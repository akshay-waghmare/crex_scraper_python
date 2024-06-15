import argparse
import sys
import cricket_data_service
from playwright.sync_api import sync_playwright
import json
import logging
from shared import scraping_tasks 
import threading

logging.basicConfig(filename='crex_scraper.log', level=logging.DEBUG, format='%(asctime)s %(message)s')

# Function to print updated text
def printUpdatedText(updatedTexts, token, url):
    for text in updatedTexts:
        score_update = {'score_update': text}
        cricket_data_service.send_cricket_data_to_service(score_update, token, url)
        logging.info(score_update)

# Function to print back and lay odds
def printOdds(backOdds, layOdds):
    logging.info("back odds are: ", backOdds)
    logging.info("lay odds are: ", layOdds)


def fetchData(url):
    """
    Fetches data from a given URL using Playwright library.

    Args:
        url (str): The URL to fetch data from.

    Returns:
        None
    """
    logging.info(f"Starting fetchData for URL: {url}")
    with sync_playwright() as p:
        try:
            logging.info("Launching browser")
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage'])
            logging.info("Browser launched successfully")
            context = browser.new_context()
            page = context.new_page()
            logging.info("Browser context and page created")

            # Get the token before entering the observation loop
            token = cricket_data_service.get_bearer_token()
            logging.info(f"Bearer token obtained: {token}")
            
            # Add a listener for page errors
            page.on('error', lambda error: logging.error(f"Uncaught error: {error.name}: {error.message}"))

            isButtonFoundFlag = False  # Initialize here
            try:
                logging.info(f"Navigating to URL: {url}")
                page.goto(url, timeout=60000)
                # here I want to wait for 30 seconds before clicking on the button
                # Wait for the oddsViewButton to be available
                isButtonFoundFlag = search_and_click_odds_button(page)
                logging.info(f"Button found: {isButtonFoundFlag}")
            except Exception as e:
                logging.error(f"Error during navigation: {e}")

            # Start the observation loop in the background
            observeTextChanges(page , isButtonFoundFlag,token,url)

            # Keep the main event loop running
            page.wait_for_timeout(1e9)

        except Exception as e:
            logging.error(f"Uncaught error: {e}")

def search_and_click_odds_button(page):
    """
    Searches for the "Odds View" button on the page and clicks on it.

    Args:
        page: The page object representing the web page.

    Returns:
        True if the button is found and clicked successfully, False otherwise.
    """
    try:
        # Wait for the "Odds View" button to appear in the DOM
        page.wait_for_selector('.odds-view-btn .view:nth-child(2)', timeout=30000)
        
        # Run JavaScript on the page to click on the "Odds View" button
        page.evaluate('''
            () => {
                const oddsViewButton = document.querySelector('.odds-view-btn .view:nth-child(2)');
                oddsViewButton.click();
            }
        ''')
        logging.info("Clicked on the Odds View button")
        return True
    except Exception as e:
        logging.error(f"Odds View button not found within the specified timeout period: {e}")
        return False

def observeTextChanges(page , isButtonFoundFlag,token,url):
    """
    Observes text changes on a web page and prints the updated texts and data.

    Args:
        page: The web page to observe.
        isButtonFoundFlag: A flag indicating whether the button is found.

    Returns:
        None
    """
    logging.info("Starting observation of text changes")
    try:
        running = True
        previousTexts = set()
        previousData = []
        previousScore = []
        while running:
            # Check if the task is marked for stopping
            if scraping_tasks.get(url, {}).get('status') == 'stopping':
                logging.info(f'Stopping scraping task for url: {url}')
                running = False
                break;
            try:
                if not isButtonFoundFlag:
                   logging.info("Buton not found, searching again") 
                   isButtonFoundFlag = search_and_click_odds_button(page)
                   logging.info(f"Button found: {isButtonFoundFlag}")

                # Evaluate JavaScript on the page to get updated texts
                updatedTexts = page.evaluate('''
                    () => {
                        const spans = document.querySelectorAll('.result-box span');
                        return Array.from(spans).map(span => span.textContent.trim());
                    }
                ''')
                logging.info(f"Updated texts: {updatedTexts}")
                # Extract CRR
                crr = page.evaluate('''
                    () => {
                        const crrElement = document.querySelector('.team-run-rate .data');
                        return crrElement ? crrElement.textContent.trim() : 'CRR not found';
                    }
                ''')
                logging.info(f"CRR: {crr}")
                
                # Extract the "KAR need 277 runs to win" text
                final_result_text = page.evaluate('''
                    () => {
                        const finalResultElement = document.querySelector('.final-result.m-none');
                        return finalResultElement ? finalResultElement.textContent.trim() : 'Final result text not found';
                    }
                ''')
                logging.info(f"Final Result Text: {final_result_text}")
                
                score = page.evaluate('''
                    () => {
                        const teamDivs = Array.from(document.querySelectorAll('.team-content'));
                        const firstTeamDiv = teamDivs.length > 0 ? [teamDivs[0]] : [];
                        return firstTeamDiv.map(div => {
                            const teamName = div.querySelector('.team-name').textContent.trim();
                            const score = div.querySelector('.runs span:nth-child(1)').textContent;
                            const over = div.querySelector('.runs span:nth-child(2)').textContent;
                            return {
                                teamName,
                                score,
                                over,
                            };
                        });
                    }
                ''')
                logging.info(f"Score: {score}")
                # Bundle the data together
                 # Use page.evaluate() to execute JavaScript within the page context
                overs_data = page.evaluate('''() => {
                    const overs = [];
                    document.querySelectorAll('div#slideOver .overs-slide').forEach(overElement => {
                        const overNumber = overElement.querySelector('span').textContent;
                        const balls = Array.from(overElement.querySelectorAll('.over-ball')).map(ball => ball.textContent);
                        const totalRuns = overElement.querySelector('.total').textContent;

                        overs.push({
                            overNumber: overNumber.trim(),
                            balls: balls,
                            totalRuns: totalRuns.trim()
                        });
                    });
                    return overs;
                }''')
                logging.info(f"Overs data: {overs_data}")
                # Print extracted data
                for over in overs_data:
                    logging.info(f"{over['overNumber']}: {' '.join(over['balls'])} (Total: {over['totalRuns']})")
        
                data_to_send = {
                    "match_update": {
                        "score": score[0] if score else {},  # Send the first score object or an empty dict if no score
                        "crr": crr,
                        "final_result_text": final_result_text
                    },
                    "overs_data": overs_data if overs_data else [],
                }
                if score != previousScore:
                    logging.info(score[0])
                    previousScore = score
                    cricket_data_service.send_cricket_data_to_service(data_to_send, token , url)
                
                if isButtonFoundFlag and 'test' in page.url:
                    logging.info("Button found, searching for odds in test for url: {url}")
                    
                    data =  page.evaluate('''
                        () => {
                            const teamDivs = Array.from(document.querySelectorAll('.fav-odd .d-flex'));
                            return teamDivs.map(div => {
                                const teamName = div.querySelector('.team-name span').textContent;
                                const odds = Array.from(div.querySelectorAll('.odd div')).map(div => div.textContent);
                                return {
                                    teamName,
                                    backOdds: odds[0],
                                    layOdds: odds[1],
                                };
                            });
                        }
                    ''')
                    # Compare data to previous data and if not the same then print
                    if data != previousData:
                        logging.info(f"Odds data changed: {data}")
                        logging.info(data)
                        #convert this data to dictionary before sending 
                        cricket_data_service.send_cricket_data_to_service(data, token,url)
                        previousData = data
                
                if isButtonFoundFlag and not 'test' in page.url:
                    try:
                        data =  page.evaluate('''
                            () => {
                                const teamDivs = Array.from(document.querySelectorAll('.fav-odd'));
                                const firstTeamDiv = teamDivs.length > 0 ? [teamDivs[0]] : [];
                                const sessionDiv = teamDivs.length == 2 ? [teamDivs[1]] : [];
                                const firstTeamData = firstTeamDiv.map(div => {
                                    const teamName = div.querySelector('.rate-team-full-name').textContent;
                                    const odds = Array.from(div.querySelectorAll('.odd div')).map(div => div.textContent);
                                    return {
                                        teamName,
                                        backOdds: odds[0],
                                        layOdds: odds[1],
                                    };
                                });
                                const sessionData = sessionDiv.length > 0 ? sessionDiv.map(div => {
                                    const sessionName = div.querySelector('.fav').textContent;
                                    const odds = Array.from(div.querySelectorAll('.yes-no-odds div')).map(div => {
                                        const option = div.querySelector('span:first-child').textContent;
                                        const value = div.querySelector('span:last-child').textContent.trim();
                                        return {
                                            option,
                                            value,
                                        };
                                    });
                                    return {
                                        sessionName,
                                        odds
                                    };
                                }) : [];
                                return {
                                    firstTeamData,
                                    sessionData
                                };
                            }
                        ''')

                        # Compare data to previous data and if not the same then print
                        if data != previousData:
                            logging.info(f"Odds data changed: {data}")
                            logging.info("here I want to check why it is not sendign ")
                            cricket_data_service.send_cricket_data_to_service(data, token,url)
                            previousData = data

                    except Exception as e:
                        logging.error(f"Error during data evaluation: {e}")
                        
                # Only print if the text content has changed
                if set(updatedTexts) != previousTexts:
                    logging.info(f"Text content changed: {updatedTexts}")
                    printUpdatedText(updatedTexts,token,url)
                    previousTexts = set(updatedTexts)

            except Exception as e:
                logging.error(f"Error during DOM manipulation: {e}")

            # Check for keyboard interrupt
            try:
                page.wait_for_timeout(2500)
            except KeyboardInterrupt:
                running = False
                logging.info("Observation loop stopped.")
                sys.exit(0)  # Exit the script with a status code of 0 (success)

    except Exception as e:
        logging.error(f"Uncaught error: {e}")

# Main function
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and observe data from a given URL.")
    parser.add_argument("url", type=str, help="The URL to observe")

    args = parser.parse_args()
    fetchData(args.url)