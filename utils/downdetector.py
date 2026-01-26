from playwright.async_api import async_playwright
import uuid


async def fetch_status_and_chart(domain):
    url = f"https://downdetector.com/status/{domain}/"
    chart_path = f"chart_{uuid.uuid4().hex}.png"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle")
            await page.evaluate("document.querySelector('#onetrust-banner-sdk')?.remove()")
            await page.evaluate("document.querySelector('#geo-redirect-root')?.remove()")

            # ✅ Dismiss cookie/privacy popup if present
            try:
                reject_button = await page.query_selector("button:has-text('Reject All')")
                if reject_button:
                    await reject_button.click()
            except:
                pass  # No popup or button not found

            # ✅ Wait for chart canvas
            canvas = await page.wait_for_selector("canvas#holder", timeout=30000)

            # ✅ Get status text
            status_el = await page.query_selector("h1.h2.page-header, h1.entry-title")
            status_text = (await status_el.inner_text()).strip() if status_el else "Status unknown"


            # ✅ Screenshot chart
            await canvas.screenshot(path=chart_path)
            return status_text, chart_path

        except Exception as e:
            print("Playwright Error:", e)
            return None, None

        finally:
            await browser.close()
