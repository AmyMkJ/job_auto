"""Fill known fields in a visible browser. Never guess or silently submit."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from .core import db, pay_check, country_for, is_high_school_role

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('job_id')
    parser.add_argument('--profile', default='data/profile.json')
    args = parser.parse_args()
    profile = json.loads(Path(args.profile).read_text())
    with db() as c:
        row = c.execute('SELECT * FROM jobs WHERE id=?', (args.job_id,)).fetchone()
    if row is None:
        raise SystemExit('Unknown job ID')
    if is_high_school_role(row['title'], row['description']):
        raise SystemExit('Blocked: this internship targets high-school students.')
    if row['term'] != 'confirmed' or not pay_check(row['description'], country_for(row['location']))['eligible']:
        raise SystemExit('Blocked: term, country or hourly pay is unconfirmed / below minimum.')
    url = urlsplit(row['url'])
    host = url.hostname or ''
    if url.scheme != 'https' or not any(host == h or host.endswith('.'+h) for h in ['greenhouse.io','lever.co']):
        raise SystemExit('Unsupported application host')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(row['url'], wait_until='domcontentloaded')
        for label, key in [('First Name','first_name'),('Last Name','last_name'),('Email','email'),('Phone','phone')]:
            field = page.get_by_label(label, exact=True)
            if profile.get(key) and field.count() == 1 and field.is_visible():
                field.fill(profile[key])
        resume = profile.get('resume_path')
        if resume and Path(resume).is_file():
            fields = page.locator('input[type=file]')
            if fields.count() == 1:
                fields.set_input_files(resume)
        print('Known fields filled where supported. Review all answers and submit in browser. No application has been recorded as submitted.')
        input('Press Enter after finishing to close browser. ')
        browser.close()

if __name__ == '__main__':
    main()
