# SmartScheule (temporary name)
SmartSchedule is a web application used to help students, workers, and managers schedule their time more wisely.
Inspired from my personal experience (always feel overwhelmed when a lot of tasks and dont know where to start).
The scheduler is synchronized with google calendar, so users can create tasks, and the scheduler can find the optimal time slot for those tasks before deadline (or minimum late days)

## Techniques used
- **Frontend**: HTML, CSS, Javascript, React
- **Backend**: Python, Fast API
- **Database**: SQLite (for now)
- **APIS**: Google Events API, Google Tasks API

## Features
- About to create event, view event, create task, and view tasks as normal scheduler
- Autonamically schedule a list of tasks into calendar aiming for minimize lateness
- AI-assisted to break down task into small tasks based on the provided task document
- Dynamically adjust existing tasks when adding new tasks and referenced to users' preference (e.g. routine of users, when the user is most productive)

## How to use
- The web application is still under development and does not support public use yet