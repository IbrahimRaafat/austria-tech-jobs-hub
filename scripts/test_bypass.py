try:
    from curl_cffi import requests as c_requests
    print("Testing curl_cffi on Stepstone...")
    r = c_requests.get("https://www.stepstone.at/work/developer/in-wien.html", impersonate="chrome120")
    print("Stepstone status:", r.status_code, "Length:", len(r.text))
except Exception as e:
    print("curl_cffi error:", e)

try:
    import cloudscraper
    print("Testing cloudscraper on Indeed...")
    scraper = cloudscraper.create_scraper()
    r = scraper.get("https://at.indeed.com/jobs?q=developer&l=Vienna")
    print("Indeed status:", r.status_code, "Length:", len(r.text))
except Exception as e:
    print("cloudscraper error:", e)
