import requests
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

MAX_PAGES = 10
START_DATE = "01-01-2022"
END_DATE = "31-12-2025"
BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
WINDOW_SECONDS = 157680000  # window_seconds = how far back to fetch (5 yrs = 157,680,000 seconds)

class Utils:
    @staticmethod
    def read_file(file_path: str):
        f = open(file_path, "r")
        content = f.read()
        f.close()
        return content

    @staticmethod
    def write_file(file_path, content):
        f = open(file_path, "w")
        f.write(content)
        f.close()

class LinkedInJobsAPI:
    def __init__(
        self,
        keyword,
        location,
        base_url = BASE_URL
    ):
        self.keyword = keyword
        self.location = location
        self.base_url = base_url

    def _build_params(self, start, window_seconds):
        return {
            "keywords": self.keyword,
            "location": self.location,
            "f_TPR": f"r{window_seconds}",
            "start": start,
        }

    def fetch_page(self, start = 0, window_seconds = WINDOW_SECONDS):
        params = self._build_params(start, window_seconds)
        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed at start={start}: {e}")
            return None

    def fetch_multiple_pages(self, total_pages, step=25):
        pages = []
        for i in range(total_pages):
            start = i * step
            print(f"[INFO] Fetching page {i+1} (start={start})")
            html = self.fetch_page(start=start)
            if html:
                pages.append(html)
        return pages


class JobParser:

    @staticmethod
    def parse_jobs_from_html(html):
        soup = BeautifulSoup(html, 'html.parser')
        job_cards = soup.select('li div.base-card.base-search-card')
        jobs = []
        for card in job_cards:
            title_tag = card.select_one('h3.base-search-card__title')
            company_tag = card.select_one('h4.base-search-card__subtitle a')
            location_tag = card.select_one('span.job-search-card__location')
            link_tag = card.select_one('a.base-card__full-link')
            date_tag = card.select_one('time.job-search-card__listdate, time.job-search-card__listdate--new')
            posted_date = date_tag['datetime'] if date_tag else None

            if title_tag and company_tag and location_tag and link_tag:
                jobs.append({
                    'title': title_tag.get_text(strip=True),
                    'company': company_tag.get_text(strip=True),
                    'location': location_tag.get_text(strip=True),
                    'link': link_tag['href'],
                    'posted_date': posted_date
                })
        return jobs


class JobFilter:
    """Filters jobs by actual posting date extracted from HTML."""

    @staticmethod
    def filter_by_date(jobs: List[Dict[str, str]], start_date, end_date):
        start_dt = datetime.strptime(start_date, "%d-%m-%Y")
        end_dt = datetime.strptime(end_date, "%d-%m-%Y")

        filtered = []
        for job in jobs:
            if job["posted_date"] is None:
                continue

            posted_dt = datetime.fromisoformat(job["posted_date"])

            if start_dt <= posted_dt <= end_dt:
                filtered.append(job)

        return filtered


class JobSaver:
    @staticmethod
    def save_to_csv(jobs, filename):
        save_path = "../data/job_data/country_and_title_wise/" + filename
        df = pd.DataFrame(jobs)
        df.to_csv(save_path, index=False)
        print(f"[SUCCESS] Saved {len(jobs)} jobs to {filename}")


class LinkedInJobScraper:
    def __init__(self, jobs_keywords=[], job_locations=[]):
        self.jobs_keywords = jobs_keywords 
        self.job_locations = job_locations 

    def run(self):
        for keyword in self.jobs_keywords:
            for location in self.job_locations:
                api = LinkedInJobsAPI(
                    keyword=keyword,
                    location=location
                )
                html_pages = api.fetch_multiple_pages(total_pages=MAX_PAGES)
                all_jobs = []
                for page in html_pages:
                    all_jobs.extend(JobParser.parse_jobs_from_html(page))

                print(f"[INFO] Total jobs scraped: {len(all_jobs)} for {keyword} in {location}")

                filtered_jobs = JobFilter.filter_by_date(
                    all_jobs,
                    start_date=START_DATE,
                    end_date=END_DATE
                )
                print(f"[INFO] Jobs after date filtering: {len(filtered_jobs)}")
                JobSaver.save_to_csv(filtered_jobs, f"{keyword}_{location}_jobs.csv")

if __name__ == "__main__":
    jobs_keywords = Utils.read_file("ai_jobs50.txt").splitlines()
    jobs_locations = Utils.read_file("job_countries.txt").splitlines()
    
    lijs = LinkedInJobScraper(
        jobs_keywords=jobs_keywords,
        job_locations=jobs_locations
    )
    lijs.run()
