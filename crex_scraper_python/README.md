# Cricket Scraper Project

## Overview
The Cricket Scraper project is designed to scrape live cricket match data from the website "https://crex.live". It provides a backend API for managing scraping tasks, storing leads, and interacting with cricket data services.

## Features
- Scrapes live match URLs and data from the target website.
- Stores scraped URLs and leads in a SQLite database.
- Provides a RESTful API for starting and stopping scraping tasks.
- Supports CORS for cross-origin requests.
- Implements logging for monitoring and debugging.

## Installation
1. Clone the repository:
   ```
   git clone https://github.com/yourusername/crex_scraper_python.git
   cd crex_scraper_python
   ```

2. Set up a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. (Optional) Install development dependencies:
   ```
   pip install -r requirements-dev.txt
   ```

5. Create a `.env` file based on the `.env.example` file to configure environment variables.

## Usage
To run the application, execute the following command:
```
python src/crex_main_url.py
```

The application will start a Flask server on `http://0.0.0.0:5000`.

## API Endpoints
- **POST /start-scrape**: Start scraping for a specific URL.
- **POST /stop-scrape**: Stop scraping for a specific URL.
- **POST /add-lead**: Add a new lead to the database.
- **GET /view-leads**: Retrieve all leads from the database.
- **PUT /update-lead/<lead_id>**: Update an existing lead.
- **DELETE /delete-lead/<lead_id>**: Delete a lead from the database.

## Contributing
Contributions are welcome! Please read the [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines on how to contribute to this project.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments
- Thanks to the contributors and the open-source community for their support and resources.