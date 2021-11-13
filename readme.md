# Queue Status Scraper Tool

Periodically scrapes a QueueStatus queue and saves
information to a MongoDB database.

Configured using the following environment variables:

- `MONGODB_URL` -- MongoDB connection URI
- `MONGODB_DB` -- MongoDB database name
- `EMAIL` -- QueueStatus email address
- `PASSWORD` -- QueueStatus password
- `QUEUE_ID` or `QUEUE_IDS` -- The ID of the queue to scrape (multiple may be specified with commas)
- `INTERVAL` -- How often to scrape in seconds
- `TIMEZONE` -- Which timezone QueueStatus is using
