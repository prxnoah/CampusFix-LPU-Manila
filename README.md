# LPU Manila CampusFix – University Portal Edition

A Flask + SQLite/MySQL university portal and CampusFix maintenance management system redesigned around the visual language of Lyceum of the Philippines University – Manila.

## What was upgraded

- LPU Manila-inspired red / gold / gray / white visual system
- University-style navigation, quick links, footer and admissions/academic sections
- LPU Manila information based on public official university pages
- Real LPU Manila address and a live OpenStreetMap campus locator centered on the campus
- Google Maps handoff for navigation
- LPU academic colleges/program examples
- Campus facilities and official office references
- CampusFix reporting, workflow, notifications and role-based dashboards retained
- ReactBits-inspired interaction layer implemented in framework-free JavaScript so the Flask/Jinja project remains easy to run
- Cursor spotlight, magnetic buttons, 3D tilt cards, scroll reveals, animated counters, marquee, scroll progress and page loading animation
- Optional Three.js hero object loaded from CDN for a lightweight 3D background effect
- Reduced-motion support
- Responsive mobile navigation and layouts

## Run

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Demo accounts

- student@campusfix.local / password123
- faculty@campusfix.local / password123
- maintenance@campusfix.local / password123
- supervisor@campusfix.local / password123
- admin@campusfix.local / password123

## Important note

This is a school/project implementation inspired by LPU Manila's publicly visible branding and information. It is **not an official LPU Manila system**, and official transactions should be completed through LPU Manila's official website.

The public university information was checked against LPU Manila's official website, including its university profile, admissions, academics, campus tour and contact information. The map uses OpenStreetMap with the LPU Manila campus centered at approximately 14.5916, 120.97783.

## Image / map attribution

The LPU campus photo used in the demo is a Wikimedia Commons image (`Lyceum of the Philippines.jpg`) licensed CC BY-SA 3.0. The page credits the source in the UI destination context. The map is embedded from OpenStreetMap.
