# Use the official Ubuntu image from the Docker Hub
FROM macubex/crex-scrapper-2:latest

# Set the working directory in the container
WORKDIR /app

COPY . /app

RUN chmod +x /app/start.sh

# Expose the port Flask is running on
EXPOSE 5000

# Set the default command to run the startup script
CMD ["/app/start.sh"]
