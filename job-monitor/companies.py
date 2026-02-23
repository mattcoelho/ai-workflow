"""Company configurations for job scraping."""

COMPANIES = [
    # Greenhouse companies
    {"name": "Automattic", "type": "greenhouse", "board_token": "automatticcareers"},
    {"name": "LaunchDarkly", "type": "greenhouse", "board_token": "launchdarkly"},
    {"name": "Honeycomb", "type": "greenhouse", "board_token": "honeycomb"},
    {"name": "Calendly", "type": "greenhouse", "board_token": "calendly"},
    {"name": "GitLab", "type": "greenhouse", "board_token": "gitlab"},
    # Ashby companies
    {"name": "1Password", "type": "playwright", "board_token": "https://jobs.ashbyhq.com/1password"},
    {"name": "Kraken", "type": "playwright", "board_token": "https://jobs.ashbyhq.com/kraken.com"},
    {"name": "Zapier", "type": "playwright", "board_token": "https://jobs.ashbyhq.com/zapier"},
    {"name": "CoreWeave (W&B)", "type": "playwright", "board_token": "https://coreweave.com/careers/weights-biases"},
    {"name": "Mattermost", "type": "playwright", "board_token": "https://mattermost.com/careers/#openings"},
    {"name": "Buffer", "type": "playwright", "board_token": "https://buffer.com/journey"},
    {"name": "Linear", "type": "playwright", "board_token": "https://linear.app/careers"},
    {"name": "Remote", "type": "playwright", "board_token": "https://remote.com/careers"},
    # Static HTML companies
    {"name": "Aha!", "type": "static", "board_token": "https://www.aha.io/company/careers/current-openings"},
    {"name": "DuckDuckGo", "type": "static", "board_token": "https://duckduckgo.com/hiring"},
    {"name": "Close", "type": "static", "board_token": "https://close.com/careers"}
    # Playwright companies (JS-rendered pages)
    # {"name": "Example", "type": "playwright", "board_token": "https://example.com/careers"},
]
