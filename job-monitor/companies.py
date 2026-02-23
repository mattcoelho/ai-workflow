"""Company configurations for job scraping."""

COMPANIES = [
    # Greenhouse companies
    {"name": "Automattic", "type": "greenhouse", "board_token": "automatticcareers"},
    {"name": "LaunchDarkly", "type": "greenhouse", "board_token": "launchdarkly"},
    {"name": "Honeycomb", "type": "greenhouse", "board_token": "honeycomb"},
    {"name": "Calendly", "type": "greenhouse", "board_token": "calendly"},
    {"name": "GitLab", "type": "greenhouse", "board_token": "gitlab"},
    # Ashby companies
    {"name": "1Password", "type": "ashby", "board_token": "1password"},
    {"name": "Kraken", "type": "ashby", "board_token": "kraken.com"},
    {"name": "Zapier", "type": "ashby", "board_token": "zapier"},
    # Static HTML companies
    {"name": "CoreWeave (W&B)", "type": "static", "board_token": "https://coreweave.com/careers/weights-biases"},
    {"name": "Mattermost", "type": "static", "board_token": "https://mattermost.com/careers/#openings"},
    {"name": "Aha!", "type": "static", "board_token": "https://www.aha.io/company/careers/current-openings"},
    {"name": "DuckDuckGo", "type": "static", "board_token": "https://duckduckgo.com/hiring"},
    {"name": "Buffer", "type": "static", "board_token": "https://buffer.com/journey"},
    {"name": "Linear", "type": "static", "board_token": "https://linear.app/careers"},
    {"name": "Close", "type": "static", "board_token": "https://close.com/careers"},
    {"name": "Remote", "type": "static", "board_token": "https://remote.com/careers"},
]
