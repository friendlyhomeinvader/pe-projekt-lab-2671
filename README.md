# pe-projekt-lab-2671
A small Python application for university room and key management.

## Installation

### Prequisites
- Docker or Docker Desktop (latest)
- docker-compose

### Quickstart Guide

This will start your app on `localhost:5000`

```
git clone https://github.com/friendlyhomeinvader/pe-projekt-lab-2671.git
cd pe-projekt-lab-2671
docker compose up --build
```


## Features

## Login
Users can log in to the application using their credentials on the Authentication screen to access the available features.

## Navigation Flow
Users can navigate between the different application screens through a clear and list style navigation system.

## Booking Flow
Users can check available booking options, select a preferred date and time slot, and submit a booking request, by 5 minute intervals. 

## Admin
Administrators have access to management features, allowing them to manage users, rooms, bookings, and system settings.

## Operator
Operator handle room keys, ensuring that only authorized users can access specific rooms.

## Extra feature
**Multibooking.** On the booking screen, a requester can check "Repeat
this slot weekly (multibooking)" when picking a time slot and choose how
many additional weeks to repeat it for (1-13, so up to 14 bookings in
one go: the picked week plus 13 more). The same room, day of week, and
time are booked for every selected week. A confirmation dialog lists the
exact dates before anything is created, and if any of the weeks would
conflict with an existing booking or a maintenance slot, nothing is
booked at all (all-or-nothing) — the conflicting date is named so the
request can be adjusted and retried.

## Documentation

### Web application
- Python, Flask
- Flask-migrate, Flask-sqlalchemy
- Jinja2 templates
- HTMX

### DBMS
- SQLite

### Tooling
- pytest
- ruff

### API documentation
API documentation (Swagger UI) can found under at [`/docs`](http://localhost:5000/docs)

## ER-diagram:
```mermaid
erDiagram
    USERS ||--o{ BOOKINGS : requests
    USERS ||--o{ MAINTENANCE_WINDOWS : creates
    USERS ||--o{ KEY_AUTHORIZATIONS : "authorized for"
    USERS ||--o{ KEY_AUTHORIZATIONS : grants
    USERS ||--o{ KEY_TRANSACTIONS : "acts as porter"
    USERS ||--o{ KEY_TRANSACTIONS : "acts as holder"
    USERS ||--o{ FAULT_TICKETS : reports
    USERS ||--o{ AUDIT_LOG : "acts as actor"

    ROOMS ||--o{ ROOM_FEATURES : offers
    FEATURES ||--o{ ROOM_FEATURES : "offered by"

    ROOMS ||--o{ KEYS : "standard key of"
    ROOMS ||--o{ MASTER_KEY_COVERAGE : "covered by"
    KEYS ||--o{ MASTER_KEY_COVERAGE : covers
    KEYS ||--o{ KEY_AUTHORIZATIONS : "authorization for"
    KEYS ||--o{ KEY_TRANSACTIONS : "issued/returned"
    KEYS ||--o{ FAULT_TICKETS : "subject of"

    ROOMS ||--o{ BOOKINGS : "booked for"
    ROOMS ||--o{ MAINTENANCE_WINDOWS : "blocked for"
    BOOKINGS ||--o{ KEY_TRANSACTIONS : "linked to"
    BOOKINGS ||--o{ BOOKING_CONFLICTS : "flagged as reservation"
    MAINTENANCE_WINDOWS ||--o{ BOOKING_CONFLICTS : "flagged as maintenance"

    ROOMS ||--o{ FAULT_TICKETS : "subject of"
    KEY_TRANSACTIONS ||--o{ FAULT_TICKETS : "raised from"
```

## Contener diagram
```mermaid
flowchart TD
    User["User / Browser"]

    subgraph Keymaster["Keymaster System"]
        
        subgraph WebApp["Flask Web Application"]
            Routes["Web / HTTP Layer\nRoutes + Blueprint"]

            Booking["Booking Domain"]
            Keys["Key Management Domain"]
            Audit["Audit Domain"]
            Admin["Administration Domain"]
            
            Models["Persistence / ORM Layer\nmodels/"]
        end

        UI["Server-rendered Web UI\nJinja2 + HTML + CSS + JS + HTMX"]

        DB[(Keymaster SQLite Database)]
    end

    User -->|"HTTP / HTTPS"| Routes

    Routes -->|"Render pages"| UI
    UI -->|"Forms / HTMX requests"| Routes

    Routes --> Booking
    Routes --> Keys
    Routes --> Audit
    Routes --> Admin

    Booking --> Models
    Keys --> Models
    Audit --> Models
    Admin --> Models

    Models -->|"SQLAlchemy"| DB
```