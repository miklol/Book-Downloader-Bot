import asyncio
import httpx
from bs4 import BeautifulSoup

async def test_search():
    url = "https://libgen.li/index.php"
    params = {
        'req': 'python',
        'open': 0,
        'res': 25,
        'view': 'simple',
        'phrase': 1,
        'column': 'def',
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as client:
        r = await client.get(url, params=params)
        soup = BeautifulSoup(r.text, 'html.parser')
        tables = soup.find_all('table')
        if len(tables) > 1:
            table = tables[1]
            rows = table.find_all('tr')
            for i, row in enumerate(rows[:3]):
                tds = row.find_all('td')
                print(f"Row {i} ({len(tds)} cols):")
                for j, td in enumerate(tds):
                    print(f"  Col {j}: {td.get_text(strip=True)[:50]}")

if __name__ == "__main__":
    asyncio.run(test_search())
