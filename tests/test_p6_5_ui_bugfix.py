import pytest
from pathlib import Path

def test_research_campaign_modal_fetches_dropdowns():
    """
    Regression test proving that the Research Campaign UI triggers
    a dynamic load of Sales Offers and ICPs to populate the dropdowns.
    """
    # 1. Verify the HTML button calls the JS function instead of just opening the modal
    with open("static/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Prove the fix is applied to the button
    assert 'onclick="openNewCampaignModal()"' in html_content
    assert 'onclick="document.getElementById(\'new-campaign-modal\').style.display=\'block\'"' not in html_content

    # 2. Verify the JS function exists and populates the specific DOM elements
    with open("static/research.js", "r", encoding="utf-8") as f:
        js_content = f.read()
    
    # Prove the JS logic fetches the APIs
    assert "fetch('/api/sales_offers')" in js_content
    assert "fetch('/api/icps')" in js_content
    
    # Prove it targets the correct dropdowns
    assert "document.getElementById('new-campaign-offer')" in js_content
    assert "document.getElementById('new-campaign-icp')" in js_content
