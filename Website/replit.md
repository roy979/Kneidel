# Kneidel - Music Guessing Game

## Overview

Kneidel is a Flask-based web application that implements a music guessing game. Players listen to audio stems and try to guess the song title. The application integrates with GitHub repositories for music package management and Spotify for additional music metadata.

## System Architecture

The application follows a traditional Flask web architecture with the following key components:

- **Backend**: Python Flask application with CORS support
- **Frontend**: HTML/CSS/JavaScript with Bootstrap styling
- **Audio Processing**: Web Audio API for client-side audio manipulation
- **Data Sources**: GitHub repository for music packages, Spotify API for metadata
- **Deployment**: Gunicorn WSGI server on Replit with auto-scaling

## Key Components

### Flask Application (`app.py`, `main.py`)
- **Purpose**: Main application logic and route handling
- **Architecture Decision**: Separated app creation from execution to support both development and production deployment
- **Rationale**: Allows for different configurations between development (`python main.py`) and production (`gunicorn main:app`)

### Audio Management (`static/js/audio.js`)
- **Purpose**: Client-side audio processing using Web Audio API
- **Architecture Decision**: Use Web Audio API instead of simple HTML5 audio elements
- **Rationale**: Provides fine-grained control over audio playback, stem mixing, and real-time audio manipulation
- **Key Features**: Audio context management, stem loading, buffer management

### Game Logic (`static/js/game.js`)
- **Purpose**: Frontend game state management and user interaction
- **Architecture Decision**: Class-based JavaScript architecture
- **Rationale**: Encapsulates game state and provides clear separation of concerns
- **Key Features**: Stage progression, score tracking, package selection

### Authentication & External Services
- **Primary Strategy**: External token server (`kneidel.onrender.com/api/tokens`)
- **Fallback Strategy**: Environment variables
- **Rationale**: Centralized credential management while maintaining local development flexibility
- **Services**: GitHub API for music packages, Spotify API for metadata

## Data Flow

1. **Package Discovery**: Application fetches available music packages from GitHub repository
2. **Package Selection**: User selects desired music packages through modal interface
3. **Audio Loading**: Client-side audio manager loads and buffers audio stems
4. **Game Progression**: Six-stage gameplay with progressive audio stem reveals
5. **Guess Validation**: User guesses are processed and scored
6. **Metadata Enhancement**: Spotify integration provides additional song information

## External Dependencies

### Core Dependencies
- **Flask**: Web framework with CORS support
- **Spotipy**: Spotify Web API integration
- **Requests**: HTTP client for GitHub API integration
- **Gunicorn**: Production WSGI server

### Frontend Dependencies
- **Bootstrap 5.3.0**: UI framework
- **Font Awesome 6.4.0**: Icons
- **Web Audio API**: Audio processing (browser native)

### Infrastructure
- **GitHub**: Music package storage and version control
- **Spotify Web API**: Music metadata
- **PostgreSQL**: Database support (configured but not actively used)

## Deployment Strategy

- **Platform**: Replit with Nix package management
- **Server**: Gunicorn with auto-scaling deployment target
- **Database**: PostgreSQL available but not currently utilized
- **Architecture Decision**: Stateless application design for horizontal scaling
- **Rationale**: Supports auto-scaling while maintaining simplicity

## Changelog
- June 20, 2025. Initial setup

## User Preferences

Preferred communication style: Simple, everyday language.