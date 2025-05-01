## Features

### Equipment Availability View

![Equipment Availability Screenshot](equipment_booking/images/avability.png)

### Equipment Booking View

![Equipment Availability Screenshot](equipment_booking/images/booking.png)

### Core Functionality

- **User Management**

  - Role-based access (Admin, Manager, Employee)
  - Department assignment
  - Profile management

- **Equipment Management**

  - Equipment type categorization
  - Quantity tracking
  - Location management
  - Availability status (active/inactive)

- **Booking System**

  - Single and recurring bookings
  - Approval workflow
  - Conflict detection
  - Calendar availability view
  - Status tracking (Pending/Approved/Rejected/Completed)

- **Notifications**

  - Real-time booking alerts
  - Status change notifications
  - System announcements

- **Reporting**
  - Usage analytics
  - Equipment utilization
  - User activity

## API Endpoints

### Authentication

'/api/auth/ '- Built-in DRF authentication endpoints

### Users

| Endpoint           | Method    | Description    | Permissions |
| ------------------ | --------- | -------------- | ----------- |
| `/api/users/'      | GET       | List all users | Admin       |
| `/api/users/'      | POST      | Create user    | Admin       |
| `/api/users/{id}/' | GET       | User details   | Owner/Admin |
| `/api/users/{id}/' | PUT/PATCH | Update user    | Owner/Admin |
| `/api/users/{id}/' | DELETE    | Delete user    | Admin       |

### Equipment

| Endpoint                            | Method | Description              | Permissions |
| ----------------------------------- | ------ | ------------------------ | ----------- |
| `/api/equipment/ '                  | GET    | List equipment           | All         |
| `/api/equipment/'                   | POST   | Create equipment         | Admin       |
| `/api/equipment/{id}/'              | GET    | Equipment details        | All         |
| `/api/equipment/{id}/availability/' | GET    | Check availability       | All         |
| `/api/equipment/available/'         | GET    | List available equipment | All         |

### Bookings

| Endpoint                     | Method | Description              | Permissions         |
| ---------------------------- | ------ | ------------------------ | ------------------- |
| `/api/bookings/'             | GET    | List bookings            | Varies by role      |
| `/api/bookings/'             | POST   | Create booking           | Employee+           |
| `/api/bookings/{id}/'        | GET    | Booking details          | Owner/Manager/Admin |
| `/api/bookings/{id}/cancel/' | POST   | Cancel booking           | Owner/Manager/Admin |
| `/api/bookings/recurring/'   | POST   | Create recurring booking | Employee+           |

### Notifications

| Endpoint                      | Method | Description        |
| ----------------------------- | ------ | ------------------ |
| /api/notifications/           | GET    | User notifications |
| /api/notifications/mark-read/ | POST   | Mark as read       |

## Setup Instructions

### Prerequisites

- Python 3.8+

Installation

Clone the repo
Setup requirements
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

go to admin
create user either make group of the permissions add the user to that 
or 
run setup_all_permsission from bookings.admin once to add the permissions for the role 
STAFF_REQUIRED SHOULD BE ACTIVE FOR ALL USERS TO LOGIN

Then you can login as specific users
