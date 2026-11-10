# Car Finder

Car Finder is a lightweight Python project for discovering affordable nearby new and certified dealer cars. It pulls listings from AutoTrader and CarGurus, filters them by price, year, mileage, and distance, and exports the results to CSV and HTML for easy browsing.

## Features

- Finds new and certified dealer vehicles within a budget
- Supports ZIP code and distance filters
- Keeps only model-year and price-eligible listings
- Merges duplicate listings by VIN or listing link
- Sorts results by best value and proximity
- Exports data as a CSV file and a searchable HTML table
- Includes a local web UI with a clickable "Run" button when served

## Setup

1. Install Python 3.
2. Set your Apify API token:

   export APIFY_TOKEN=apify_api_xxx

3. Run the script from the project folder.

## Usage

Basic run:

```bash
python3 car_finder.py
```

With custom budget and radius:

```bash
python3 car_finder.py --budget 25000 --zip 94538 --radius 50
```

Serve the HTML page locally:

```bash
python3 car_finder.py --serve
```

This starts a local server so the interface can refresh data and use the Run button.

## Output files

The app writes these files to the project folder:

- cars.csv
- cars.html

## Notes

- The script uses the Python standard library only.
- It is designed for dealer inventory searches under a target budget near a given ZIP code.
- It filters results to the selected model years and nearby distances before generating the final list.
