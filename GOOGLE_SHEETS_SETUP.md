# Google Sheets Integration Setup Guide

To allow the Winterfell Arena Esports bot to read and write to your Google Sheets, you need to set up a **Google Service Account**. Follow these steps carefully.

## Step 1: Create a Google Cloud Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click on the project dropdown at the top left and select **"New Project"**.
3. Name your project (e.g., "Winterfell Arena Esports Bot") and click **Create**.
4. Select your new project from the dropdown.

## Step 2: Enable APIs
1. In the sidebar, go to **APIs & Services > Library**.
2. Search for **"Google Sheets API"** and click on it.
3. Click **Enable**.
4. Go back to the Library.
5. Search for **"Google Drive API"** and click on it.
6. Click **Enable**.

## Step 3: Create a Service Account
1. In the sidebar, go to **APIs & Services > Credentials**.
2. Click **+ CREATE CREDENTIALS** at the top and select **Service Account**.
3. **Service account details**:
   - Name: `winterfell-arena-esports-bot` (or anything you like).
   - Description: "Bot integration".
   - Click **Create and Continue**.
4. **Grant this service account access to project**:
   - Role: Select **Editor** (Basic > Editor).
   - Click **Continue**.
5. **Grant users access**: Leave blank and click **Done**.

## Step 4: Download the JSON Key
1. You should now see your new service account in the "Service Accounts" list (under Credentials).
2. Click on the **pencil icon** (Edit) or the email address of the service account.
3. Go to the **Keys** tab at the top.
4. Click **ADD KEY** > **Create new key**.
5. Select **JSON** and click **Create**.
6. A file will automatically download to your computer.

## Step 5: Configure the Bot
1. **Rename** the downloaded file to `service_account.json`.
2. **Move** this file into the main folder of your bot (where `app.py` is located).
   - *Note: Do NOT share this file with anyone. It contains your private credentials.*

## Step 6: Share the Sheet
1. Open your `service_account.json` file with a text editor (Notepad, VS Code).
2. Look for the `"client_email"` field (e.g., `winterfell-arena-esports-bot@your-project.iam.gserviceaccount.com`).
3. **Copy** this email address.
4. Open the Google Sheet you want the bot to use.
5. Click the **Share** button at the top right.
6. **Paste** the service account email and give it **Editor** access.
7. Click **Send** (unchecked "Notify people" if you want).

## Step 7: Update Bot Config
1. Open your Google Sheet.
2. Look at the URL in your browser address bar:
   `https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0`
3. The long string of random characters between `/d/` and `/edit` is your **Sheet ID**.
   - Example ID: `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms`
4. Copy this ID.
5. Open `app.py` in your bot folder.
6. Find the line `GOOGLE_SHEET_ID = "..."` and paste your ID there.

## Step 8: Sheet Headers
Ensure your Google Sheet (Sheet1) has the following headers in the first row to keep things organized:
1. Event ID
2. Tournament
3. Mode
4. Round
5. Team 1
6. Team 2
7. Date
8. Time
9. Judge
10. Recorder
11. Winner
12. Score
13. Remarks
