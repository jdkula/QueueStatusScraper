# Queue Status Scraper Tool

Periodically scrapes a QueueStatus queue and saves
information to a MongoDB database.

Configured using the following environment variables:

- `MONGODB_URL` -- MongoDB connection URI
- `MONGODB_DB` -- MongoDB database name
- `EMAIL` -- QueueStatus email address
- `PASSWORD` -- QueueStatus password
- `QUEUE_ID` -- The ID of the queue to scrape
- `INTERVAL` -- How often to scrape in seconds
- `TIMEZONE` -- Which timezone QueueStatus is using
