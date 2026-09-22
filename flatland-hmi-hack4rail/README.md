# Flatland HMI

![Flatland HMI](flatland-hmi.png)

A simple prototype demonstrating how to create a Human-Machine Interface (HMI) that can interact with a Flatland simulation environment. This repository showcases the integration between a web-based frontend and a Python backend running Flatland railway simulations.

## Demo

https://github.com/user-attachments/assets/6cec2f96-a897-462d-9cb6-9f79216a0436


## Overview

This project consists of:

- **Frontend**: An Angular application that provides a visual interface for viewing and controlling Flatland simulations
- **Backend**: A FastAPI server that manages the Flatland environment and exposes REST APIs for interaction

The HMI allows users to visualize railway networks, observe train movements, and control the simulation through step-by-step execution or continuous playback. The interface provides comprehensive information about actual train runs through real-time tracking and historical data visualization. Additionally, it displays alternative route variants that can be selected when critical decisions need to be made, such as during train malfunctions, equipment failures, or unexpected delays.

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run start
```

Open your browser and navigate to `http://localhost:4200` to interact with the Flatland simulation.

## Features

- Real-time visualization of railway environments with train movement tracking
- Interactive Marey diagram showing train trajectories over time and distance
- Train movement tracking with directional indicators and malfunction detection
- Dynamic route planning with selectable variants for decision support
- Interactive simulation controls (step, play, pause, reset)
- Alternative route selection interface for handling disruptions and malfunctions
- Multiple policy implementations (random, deadlock avoidance)
- RESTful API for environment interaction

## Technologies

- **Frontend**: Angular, TypeScript, SCSS
- **Backend**: FastAPI, Python, Flatland-RL
- **Communication**: HTTP REST APIs with CORS support
