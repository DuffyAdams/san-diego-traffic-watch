"""Read-only XML/HTML comparison with at most three HTML detail requests."""
import json

import requests
from bs4 import BeautifulSoup

from backend.config import CHP_SCRAPE_URL, HTTP_TIMEOUT_SECONDS, HEADERS
from backend.incident_facts import narrative_lines
from backend.scrapers.chp import scrape_chp_xml, _get_viewstate, _process_row, compare_snapshots


def main():
    xml = scrape_chp_xml()
    response = requests.get(CHP_SCRAPE_URL, headers=HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', id='gvIncidents')
    if table is None:
        raise RuntimeError('CHP table unavailable')
    headers = [th.get_text(strip=True) for th in table.find_all('th')]
    state = _get_viewstate(response.text)
    samples = []
    for i, row in enumerate(table.find_all('tr')[1:4]):
        record = _process_row(i, row, headers, state)
        if record:
            samples.append(record)
    ids = {r['No.'] for r in samples}
    xml_sample = [r for r in xml if r['No.'] in ids]
    report = compare_snapshots(samples, xml_sample)
    report['xml_total'] = len(xml)
    report['html_total'] = len(table.find_all('tr')) - 1
    report['samples'] = []
    for html in samples:
        match = next((r for r in xml_sample if r['No.'] == html['No.'] and r['Area'] == html.get('Area')), None)
        report['samples'].append({
            'id': html['No.'], 'details_available': html.get('DetailsAvailable'),
            'narrative_matches': bool(match) and narrative_lines(html.get('Details')) == narrative_lines(match['Details']),
            'coordinates_match': bool(match) and all(html.get(k) == match.get(k) for k in ('Latitude', 'Longitude')),
        })
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
