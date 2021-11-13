# Queue Status Scraper Tool

Periodically scrapes a QueueStatus queue and saves
information to a MongoDB database.

Configured using the following environment variables:

Required:

- `MONGODB_URI` -- MongoDB connection URI
- `MONGODB_DBNAME` -- MongoDB database name
- `QUEUE_ID` or `QUEUE_IDS` -- The ID of the queue to scrape (multiple may be specified with commas)
- `INTERVAL` -- How often to scrape in seconds

Optional:

- `EMAIL` -- QueueStatus email address (without credentials it scrapes the public-facing webpage, which will give less information)
- `PASSWORD` -- QueueStatus password
- `TIMEZONE` -- Which timezone QueueStatus is using (defaults to the local timezone of the computer, which is probably wrong)
