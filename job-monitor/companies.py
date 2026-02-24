"""Company configurations for job scraping."""

COMPANIES = [
    # Greenhouse companies
    {"name": "Automattic", "type": "greenhouse", "board_token": "automatticcareers"},
    {"name": "LaunchDarkly", "type": "greenhouse", "board_token": "launchdarkly"},
    {"name": "Honeycomb", "type": "greenhouse", "board_token": "honeycomb"},
    {"name": "Calendly", "type": "greenhouse", "board_token": "calendly"},
    {"name": "GitLab", "type": "greenhouse", "board_token": "gitlab"},
    {"name": "Human Interest", "type": "greenhouse", "board_token": "humaninterest"},
    # Ashby companies
    {"name": "1Password", "type": "playwright", "board_token": "https://jobs.ashbyhq.com/1password"},
    {"name": "Kraken", "type": "playwright", "board_token": "https://jobs.ashbyhq.com/kraken.com"},
    {"name": "Zapier", "type": "playwright", "board_token": "https://jobs.ashbyhq.com/zapier"},
    {"name": "CoreWeave (W&B)", "type": "playwright", "board_token": "https://coreweave.com/careers/weights-biases"},
    {"name": "Mattermost", "type": "playwright", "board_token": "https://mattermost.com/careers/#openings"},
    {"name": "Buffer", "type": "playwright", "board_token": "https://buffer.com/journey"},
    {"name": "Linear", "type": "playwright", "board_token": "https://linear.app/careers"},
    {"name": "Remote", "type": "playwright", "board_token": "https://remote.com/careers"},
    {"name": "Coinbase", "type": "playwright", "board_token": "https://www.coinbase.com/careers/positions"},
    {"name": "Shopify", "type": "playwright", "board_token": "https://www.shopify.com/careers"},
    {"name": "Stripe", "type": "playwright", "board_token": "https://stripe.com/jobs/search"},
    {"name": "Webflow", "type": "playwright", "board_token": "https://webflow.com/careers"},
    {"name": "Twilio", "type": "playwright", "board_token": "https://www.twilio.com/en-us/company/jobs"},
    {"name": "Sourcegraph", "type": "playwright", "board_token": "https://sourcegraph.com/jobs"},
    {"name": "Dropbox", "type": "playwright", "board_token": "https://jobs.dropbox.com/all-jobs"},
    {"name": "Airbnb", "type": "playwright", "board_token": "https://careers.airbnb.com/positions/"},
    {"name": "Akamai Technologies", "type": "playwright", "board_token": "https://fa-extu-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs"},
    {"name": "Alliants", "type": "playwright", "board_token": "https://alliants.careers.hibob.com/jobs"},
    {"name": "Bonterra", "type": "playwright", "board_token": "https://bonterra.wd1.myworkdayjobs.com/bonterratech"},
    {"name": "Dayforce", "type": "playwright", "board_token": "https://jobs.dayforcehcm.com/en-US/mydayforce/alljobs"},
    {"name": "HubSpot", "type": "playwright", "board_token": "https://www.hubspot.com/careers/jobs?page=1"},
    {"name": "Sinch", "type": "playwright", "board_token": "https://iaings.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs"},
    # {"name": "Synoptek", "type": "playwright", "board_token": "https://careers.synoptek.com/jobs"},
    {"name": "Toast", "type": "playwright", "board_token": "https://careers.toasttab.com/jobs/search"},
    # Static HTML companies
    {"name": "Aha!", "type": "static", "board_token": "https://www.aha.io/company/careers/current-openings"},
    {"name": "DuckDuckGo", "type": "static", "board_token": "https://duckduckgo.com/hiring"},
    {"name": "Close", "type": "static", "board_token": "https://close.com/careers"}
    # Playwright companies (JS-rendered pages)
    # {"name": "Example", "type": "playwright", "board_token": "https://example.com/careers"},
]
