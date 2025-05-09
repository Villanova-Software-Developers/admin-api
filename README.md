﻿# Optima Admin Dashboard

## Overview
The Optima Admin Dashboard provides administrators with tools to manage the task-based screentime reward system. This dashboard will primarily focus on basic user and post management, and simple analytics to monitor app usage and effectiveness.

## Core Capabilities

### Admin Authentication
- Admin registration (with special key)
- Admin login
- Session management via JWT


### Post Management
- View all posts
- Delete posts
- Edit post content
- Remove comments from posts


### User Management
- View all users
- Delete users
- Suspend users
- View user posts

### Basic Analytics
- Count of posts created in a time period
- Count of users registered in a time period
- Count of comments in a time period


### Admin Logging
- Track admin actions
- View admin activity logs

## Technical Implementation

### API Endpoints
The admin dashboard will use a dedicated set of API endpoints with restricted access, implemented using Flask to maintain consistency with the existing backend.

### Authentication & Authorization
- Simple but secure authentication system
- Single admin role with full access to all admin features
- Logging of important admin actions

### Frontend Components
- Simple dashboard interface built with React
- Basic data visualizations for analytics
- Filterable tables for viewing tasks, users, and posts
- Forms for creating and editing tasks

## Development Roadmap

### Phase 1: Basic Setup
- Create admin authentication system
- Implement task management features
- Set up the admin dashboard layout

### Phase 2: User Management
- Implement user viewing capabilities
- Add ability to reset passwords and suspend accounts
- Create user search functionality

### Phase 3: Simple Analytics
- Implement basic analytics dashboard
- Show key metrics about app usage
- Display task completion statistics

## Security Considerations
- Admin API endpoints secured with proper authentication
- Admin registration requiring a special access key
- Basic logging of admin actions for auditing purposes
