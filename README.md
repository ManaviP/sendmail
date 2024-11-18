# Full-Stack Email Dashboard

This application allows users to upload CSV files, create personalized email templates with dynamic placeholders, and send emails either immediately or scheduled for later. It  provides detailed email analytics, and includes features like throttling and scheduling.

---

## Table of Contents

- [Setup and Configuration](#setup-and-configuration)
  - [Install Dependencies](#install-dependencies)
  - [Backend Configuration](#backend-configuration)
  - [Email Scheduling and Throttling](#email-scheduling-and-throttling)
- [Usage Instructions](#usage-instructions)
  - [Upload CSV File](#upload-csv-file)
  - [Write Email Template](#write-email-template)
  - [Preview Template](#preview-template)
  - [Schedule Emails](#schedule-emails)
  - [Send Emails Immediately](#send-emails-immediately)
  - [Clear Data](#clear-data)
- [License](#license)

---

## Setup and Configuration

### 1. *Install Dependencies*

Ensure that you have Node.js (for the front-end) and Python 3.x (for the back-end) installed on your system. Then, run the following commands to install all required dependencies:

For the front-end:
```bash
npm install
npm start
``` 

For the back-end:
```bash
pip install -r requirements.txt
flask run
```

### 2. *Backend Configuration*

You need to set up the backend with routes for handling email sending, file uploads, and analytics. It uses Express for the backend server and SQLAlchemy (or a similar ORM) for database interaction.

- POST /upload_file: For uploading CSV files with email data.
- POST /send_emails: For sending emails immediately or scheduling them.
- GET /detailed_analytics: For fetching email analytics (e.g., success, failures, pending).

Configure the backend with the correct base URL.

### 3. *Email Scheduling and Throttling*

You can configure email scheduling and throttling in the backend as follows:

- *Scheduling*: Emails can be scheduled by specifying a scheduled_time in the request body in ISO format.
  
Example for scheduling:
json
{
  "template": "Hello {name}, your order ID is {order_id}",
  "rows": [{"name": "John", "order_id": "123"}],
  "scheduled_time": "2024-11-20T12:00:00Z",
  "send_now": false
}


- *Throttling*: To throttle email sending (to avoid rate limits), specify rate_limit_per_minute to control how many emails are sent per minute. This can be configured using a queueing system like [Bull](https://www.npmjs.com/package/bull) for better control.

---

## Usage Instructions

### 1. *Upload CSV File*
To upload a CSV file containing email recipient data:

- Navigate to the *Upload CSV File* section.
- Select the CSV file and click *Upload*. The application will detect the columns and rows and display them for further actions.

### 2. *Write Email Template*
- Enter an email template using placeholders (e.g., {name}, {order_id}) for dynamic data.
- The columns in your CSV file will be used to replace these placeholders dynamically. Example template:

text
Hello {name}, your order ID is {order_id}.


### 3. *Preview Template*
- After writing the template, a preview will show the email with data from the first row of your CSV file.

### 4. *Schedule Emails*
- In the *Scheduled Time* input, select a future time for the email to be sent.
- Ensure the selected time is in the future to avoid errors.
- Click *Schedule Email* to schedule it.

### 5. *Send Emails Immediately*
- Click *Send Now* to send emails immediately to all recipients.

### 6. *Clear Data*
- Use the *Clear Data* button to reset the form and remove uploaded files, templates, and any other data.

---

## Example Requests

### 1. *Request to Upload a CSV File*

To upload a CSV file, make a POST request to /upload_file:

bash
curl -X POST -F "file=@emails.csv" http://localhost:5000/upload_file


*CSV Format*:

| email                | subject        |
|----------------------|----------------|
| example1@example.com | Subject 1      |
| example2@example.com | Subject 2      |

### 2. *Request to Send Emails*

To send emails with throttling and scheduling:

json
{
  "template": "Hello {name}, your order is {order_status}",
  "scheduled_time": "2024-11-20T12:00:00Z",
  "rate_limit_per_minute": 10
}

### login and register is not retrieved in any page for now

3. *Request to Register User*

json
{
  "email": "user@example.com",
  "password": "password123"
}


 4. *Request to Login User*

json
{
  "email": "user@example.com",
  "password": "password123"
}


---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
