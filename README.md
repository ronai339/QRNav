# QRNav – Indoor Navigation and Admin Tool

QRNav is a graph-based indoor navigation web application using QR codes to assist navigation. 
It models a building as a graph of rooms, nodes, and edges,
then finds the best route between two locations 
and turns the result into readable navigation instructions.
It also lets the administrator and operators maintain the building map dynamically.

The project is implemented with Flask, SQLite, and NetworkX.

---

## Features
- Indoor route planning based on a graph model
- Room-to-room navigation with turn-by-turn instructions
- QR-based start point input
- Room, node, and edge management in a web interface
- Admin and operator roles with permission checks
- CSV import/export for graph data
- Change history for graph modifications
- Basic test coverage for database and navigation logic
- English/Hungarian language switching
- Interactive graph visualizer

---

## Requirements

- Python 3.9+
- Flask
- SQLite
- networkx
- Jinja2 (used by Flask)
- pytest (for running tests)

---

## Tech stack

- Backend: Flask
- Database: SQLite
- Graph processing: NetworkX
- Frontend assets: HTML templates, CSS, JavaScript
- Build tooling: Vite, Tailwind CSS, PostCSSTech stack
- Backend: Flask
- Database: SQLite
- Graph processing: NetworkX
- Frontend assets: HTML templates, CSS, JavaScript
- Build tooling: Vite, Tailwind CSS, PostCSS

---

## Project Structure
```
qrnav/
├── app/
│   ├── auth/
│   ├── db/
│   ├── services/
│   ├── static/
│   ├── templates/
│   ├── utils/
│   └── routes.py
├── data/
├── data_management_scripts/
├── instance/
├── tests/
├── run.py
└── README.md
```
---

## Main idea

The application represents the building as a graph:
- nodes = key locations inside the building
- edges = walkable connections between nodes
- rooms = user-facing room identifiers mapped to graph nodes

When a user enters a starting room and a destination room, QRNav:
- resolves both rooms to graph nodes,
- computes the shortest path,
- translates the path into human-readable steps,
- displays the route in the web interface.

---

## Features in detail

### Navigation

The navigation engine builds a graph from the database and uses 
weighted pathfinding to determine a route.
The result is converted into step-by-step instructions that are 
easier to follow than raw node IDs.

### QR input

The system supports QR-based input for the starting location.
In practice, this can be used to simulate or support scanning 
the current room before requesting a destination.

### Role-based access

The application includes:
- admin access for full management
- operator access with restricted permissions
Password storage uses hashing instead of plain text.

### Data management

The project includes helper scripts for:
- exporting database tables to CSV
- importing seed data from CSV (more on that further down)
- maintaining graph data outside the web interface

### Testing

The repository includes tests for database setup, graph loading, 
pathfinding, instruction generation, and authentication behavior.

Run all tests with
```bash
pytest
```
or by manually running the tests/test_graph.py file.

---

## Installation
### 1. Create and activate a virtual environment
```bash
python -m venv .venv
```
Windows:
```bash
.venv\Scripts\activate
```
macOS/Linux:
```bash
source .venv/bin/activate
```
### 2. Install dependencies
```bash
pip install -r requirements.txt
```
### 3. Start the program
```bash
python run.py
```
By default, the app runs locally on Flask’s development server.

---

## Usage

1. Open the homepage in your browser. 
2. Enter a starting room or use the QR-based start input. 
3. Enter the destination room. 
4. View the computed route and navigation instructions.

Admin and operator users can also manage graph data through the protected interface.

### Default administrator login data:
- Username: admin
- Password: adminpass

---

## Database and seed data

The project uses SQLite databases stored in the instance/ folder.

If you need to populate the database with dummy data, 
import the CSV files in data/seed/ as follows:
1. Log in as admin.
2. On the admin home page click "Manage Nodes" ("Csúcsok kezelése").
3. Click "Upload & Import"
4. In the project folder qrnav navigate to data/seed.
5. Select nodes.csv to import dummy data for nodes.
6. Go back to the admin homepage and click "Manage Edges" ("Élek kezelése").
7. Repeat steps 3 and 4, then select edges.csv to import dummy data for edges. 
8. Go back to the admin homepage and click "Manage Rooms" ("Helyiségek kezelése").
9. Repeat steps 3 and 4, then select rooms.csv to import dummy data for rooms.

Alternatively, you can run the following file to import the dummy data for nodes, 
edges and rooms all at once: data_management_scripts/seed_db.py

You can reset the database to an empty state by running the following file:
app/db/migrations/db_setup.py

---

## Notes for thesis use

This project was developed as part of a thesis on graph-based indoor navigation.
The implementation focuses on a practical and extendable navigation system 
rather than a full commercial building-management platform.

---

#### Author: Rónai Virág