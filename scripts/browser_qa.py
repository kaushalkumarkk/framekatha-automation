"""Exercise the real frontend against an isolated PostgreSQL schema.

Run from the repository root: python -m scripts.browser_qa
External AI responses are deterministic fixtures; no paid services are called.
"""

import json
import os
import socket
import threading
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import uvicorn
from dotenv import load_dotenv
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from ai.feedback import EditOperation, FeedbackOperations
from api.main import app
from api.routes import feedback, scripts
from core.config import get_settings
from core.db import Base, get_db, get_session_factory
from invoicing.service import studio_today
from tests.test_scripts import sample_script


def main():
    load_dotenv()
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        raise RuntimeError("Set TEST_DATABASE_URL to a dedicated local PostgreSQL database")
    engine = create_engine(url)
    schema = "browser_" + uuid4().hex
    with engine.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(isolated)
    factory = sessionmaker(isolated, expire_on_commit=False)

    def get_test_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = get_test_db
    app.dependency_overrides[get_session_factory] = lambda: factory
    original_script, original_feedback = scripts.generate_json, feedback.parse_feedback
    scripts.generate_json = lambda *_: sample_script()
    feedback.parse_feedback = lambda _: FeedbackOperations(
        operations=[
            EditOperation(operation="remove", scene_id="scene-1", reason="QA client feedback"),
        ]
    )
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, access_log=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    errors = []
    output = Path(".local")
    output.mkdir(exist_ok=True)
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1080})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{port}")
            page.get_by_label("Studio access key").fill(get_settings().api_key.get_secret_value())
            page.get_by_role("button", name="Enter the studio").click()
            expect(page.get_by_role("heading", name="A clear view of the studio.")).to_be_visible()

            page.get_by_role("link", name="Lead inbox", exact=True).click()
            page.get_by_role("button", name="+ Add lead", exact=True).click()
            dialog = page.get_by_role("dialog")
            dialog.get_by_label("Business name", exact=True).fill("Kolkata Creative <img src=x>")
            dialog.get_by_label("Email", exact=True).fill("qa-lead@example.com")
            dialog.get_by_role("button", name="Add lead", exact=True).click()
            expect(dialog).not_to_be_visible()
            expect(page.get_by_text("Kolkata Creative <img src=x>", exact=True)).to_be_visible()
            assert page.locator("#content img").count() == 0, "Lead names must be escaped"

            page.get_by_role("link", name="Projects", exact=True).click()
            page.get_by_role("button", name="+ New project", exact=True).click()
            dialog.get_by_label("Project name", exact=True).fill("The Kolkata Launch")
            dialog.get_by_label("Client / business name").fill("QA Client")
            dialog.get_by_label("The brief", exact=True).fill("A warm, cinematic launch film.")
            dialog.get_by_label("Required skills, separated by commas").fill("acting, bengali")
            dialog.get_by_label("Maximum fee per talent (INR)").fill("10000")
            dialog.get_by_label("Shoot date", exact=True).fill(
                (studio_today() + timedelta(days=10)).isoformat()
            )
            dialog.get_by_label("Call time (IST)").fill("09:00")
            dialog.get_by_label("Shoot location").fill("Kolkata studio")
            dialog.get_by_label("Cinematographer", exact=True).fill("QA Camera")
            dialog.get_by_role("button", name="Create project", exact=True).click()
            expect(dialog).not_to_be_visible()

            page.get_by_role("link", name="Talent library", exact=True).click()
            page.get_by_role("button", name="+ Add talent", exact=True).click()
            dialog.get_by_label("Full name", exact=True).fill("QA Performer")
            dialog.get_by_label("Email", exact=True).fill("qa-actor@example.com")
            dialog.get_by_label("Skills, separated by commas", exact=True).fill("acting, bengali")
            dialog.get_by_label("Fee rate (INR)").fill("5000")
            dialog.get_by_role("button", name="Save talent", exact=True).click()
            expect(dialog).not_to_be_visible()

            page.get_by_role("link", name="Projects", exact=True).click()
            page.get_by_role("link", name="Open project").click()
            page.get_by_role("button", name="Find talent", exact=True).first.click()
            dialog.get_by_role("button", name="Select", exact=True).click()
            dialog.get_by_role("button", name="Add to selection", exact=True).click()
            expect(dialog).not_to_be_visible()
            page.get_by_role("button", name="Prepare client packet", exact=True).click()
            expect(dialog.get_by_role("heading", name="Client packet prepared.")).to_be_visible()
            page.get_by_role("button", name="Close dialog", exact=True).click()
            page.get_by_role("button", name="Record decision", exact=True).click()
            dialog.get_by_label("Approved / reviewed by").fill("QA Client")
            dialog.get_by_role("button", name="Record decision", exact=True).click()
            expect(dialog).not_to_be_visible()
            with page.expect_download() as info:
                page.get_by_role("link", name="Download call sheet").click()
            assert info.value.suggested_filename == "call-sheet.pdf"

            page.get_by_role("button", name="Customer pattern", exact=True).click()
            dialog.get_by_label("Dialogue language", exact=True).fill("Hindi")
            dialog.get_by_label("Topic", exact=True).fill("Salon launch")
            dialog.get_by_label("Number of characters", exact=True).fill("2")
            dialog.get_by_label("Shoot setting", exact=True).select_option("indoor")
            dialog.get_by_label("Recurring story structure / pattern").fill("Problem, demo, CTA")
            dialog.get_by_role("button", name="Save customer pattern", exact=True).click()
            expect(dialog).not_to_be_visible()
            page.get_by_role("button", name="Generate script", exact=True).first.click()
            expect(dialog.get_by_label("Dialogue language", exact=True)).to_have_value("Hindi")
            dialog.get_by_role("button", name="Generate draft", exact=True).click()
            expect(dialog).not_to_be_visible()
            expect(page.get_by_role("heading", name="A New Beginning")).to_be_visible()
            page.get_by_role("button", name="Import script", exact=True).click()
            dialog.get_by_label("Production script JSON", exact=True).set_input_files(
                {
                    "name": "script.json",
                    "mimeType": "application/json",
                    "buffer": sample_script().model_dump_json().encode(),
                }
            )
            dialog.get_by_role("button", name="Import script", exact=True).click()
            expect(dialog).not_to_be_visible()
            expect(page.get_by_text("Draft v2", exact=False)).to_be_visible()
            page.get_by_role("button", name="Customer pattern", exact=True).click()
            expect(dialog.get_by_label("Topic", exact=True)).to_have_value("Salon launch")
            expect(dialog.get_by_label("Number of characters", exact=True)).to_have_value("2")
            dialog.get_by_role("button", name="Cancel", exact=True).click()

            page.get_by_role("link", name="Edit review", exact=True).click()
            page.get_by_role("button", name="+ Parse feedback", exact=True).click()
            dialog.get_by_label("Feedback or voice transcript").fill("Remove scene-1")
            dialog.get_by_role("button", name="Parse for review", exact=True).click()
            expect(dialog).not_to_be_visible()
            page.get_by_role("button", name="Review operations", exact=True).click()
            dialog.get_by_label("Reviewed by", exact=True).fill("QA Editor")
            dialog.get_by_role("button", name="Record review", exact=True).click()
            expect(dialog).not_to_be_visible()

            page.get_by_role("link", name="Invoices", exact=True).click()
            page.get_by_role("button", name="+ Add invoice", exact=True).click()
            dialog.get_by_label("Invoice reference", exact=True).fill("QA-INV-15")
            dialog.get_by_label("Amount (project currency)").fill("25000")
            dialog.get_by_label("Due date", exact=True).fill(
                (studio_today() - timedelta(days=16)).isoformat()
            )
            dialog.get_by_role("button", name="Save & evaluate", exact=True).click()
            expect(dialog).not_to_be_visible()
            expect(page.get_by_text("DRAFT — HUMAN APPROVAL REQUIRED", exact=False)).to_be_visible()
            page.get_by_role("button", name="Review draft", exact=True).click()
            dialog.get_by_label("Reviewed by", exact=True).fill("QA Owner")
            dialog.get_by_role("button", name="Record review", exact=True).click()
            expect(dialog).not_to_be_visible()
            page.get_by_role("button", name="Review", exact=True).click()
            try:
                dialog.wait_for(state="visible", timeout=5000)
            except Exception:
                print("Invoice dialog error: " + page.locator("#toast").inner_text())
                raise
            dialog.locator('select[name="status"]').select_option("paid")
            dialog.get_by_role("button", name="Update status", exact=True).click()
            expect(dialog).not_to_be_visible()

            page.get_by_role("link", name="Discovery", exact=True).click()
            expect(page.get_by_role("heading", name="Discovery history")).to_be_visible()
            page.get_by_role("link", name="Workspace settings", exact=True).click()
            expect(page.get_by_role("heading", name="Local configuration")).to_be_visible()
            page.get_by_role("link", name="Overview", exact=True).click()
            expect(page.get_by_role("heading", name="A clear view of the studio.")).to_be_visible()
            page.mouse.move(1200, 100)
            page.screenshot(
                path=str(output / "browser-overview.png"), full_page=True, animations="disabled"
            )
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(300)  # Let the responsive navigation transition finish.
            page.get_by_role("button", name="Toggle navigation").click()
            page.get_by_role("link", name="Lead inbox", exact=True).click()
            expect(page.get_by_role("heading", name="Lead inbox", exact=True)).to_be_visible()
            page.get_by_role("button", name="Toggle navigation").click()
            page.get_by_role("link", name="Overview", exact=True).click()
            expect(page.get_by_role("heading", name="A clear view of the studio.")).to_be_visible()
            page.wait_for_timeout(300)
            page.screenshot(
                path=str(output / "browser-mobile.png"), full_page=True, animations="disabled"
            )
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            print(
                json.dumps(
                    page.evaluate("""() => ({responsive: {
              viewport: innerWidth,
              content: document.querySelector('#content').getBoundingClientRect().width,
              heading: document.querySelector('.page-heading').getBoundingClientRect().width,
              sidebar: document.querySelector('#sidebar').classList.contains('open')
            }})""")
                )
            )
            browser.close()
        print(
            json.dumps(
                {
                    "browser_qa": "passed",
                    "javascript_errors": errors,
                    "screenshots": [
                        str(output / "browser-overview.png"),
                        str(output / "browser-mobile.png"),
                    ],
                }
            )
        )
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
        app.dependency_overrides.clear()
        scripts.generate_json, feedback.parse_feedback = original_script, original_feedback
        with engine.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


if __name__ == "__main__":
    main()
