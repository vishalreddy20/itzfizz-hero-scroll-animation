# Itzfizz Hero – Scroll-Driven Animation

A high-performance, production-ready hero section with scroll-triggered GSAP animations. Built with Next.js 14, React 18, GSAP ScrollTrigger, Tailwind CSS, and Bootstrap. Optimized for Vercel, Netlify, and GitHub Pages deployment.

## 🎯 Project Overview

This project showcases advanced scroll-driven animation techniques using GSAP ScrollTrigger. The hero section features:
- Staggered text animations on page load
- Smooth parallax car image movement
- Progressive dark overlay intensification
- Letter dissolution effects
- Animated statistics carousel
- Premium grain texture overlay
- Fully responsive design with mobile optimization

**Live Demo:** [GitHub Pages](https://vishalreddy20.github.io/itzfizz-hero-scroll-animation)

Scroll down to see all animations in action!

## ✨ Features

### Visual Effects
- ✅ **Staggered headline letter animations** on page load (120ms per letter)
- ✅ **Smooth car image parallax** – moves and scales dynamically with scroll
- ✅ **Dark overlay gradient** that intensifies as you scroll
- ✅ **Letter dissolution effect** – headline letters fade and spread during scroll
- ✅ **Stats carousel** – statistics slide out in sync with scroll progress
- ✅ **Animated grid background** and accent glow effects
- ✅ **Grain texture overlay** for premium visual quality

### Technical Features
- ✅ **Zero layout shifts** – optimized CLS (Cumulative Layout Shift)
- ✅ **Accessibility enhancements** – semantic HTML, ARIA labels, keyboard support
- ✅ **Cross-browser compatible** – tested on modern browsers
- ✅ **Fully responsive** – mobile-first design, clamps for typography
- ✅ **Static export ready** – deploys to GitHub Pages and Netlify instantly
- ✅ **Bootstrap 5 integration** – responsive grid system for stats section
- ✅ **WordPress template included** – easy porting to WordPress themes

## 🚀 Quick Start

### Prerequisites
- Node.js 20 or later
- npm or yarn package manager

### Installation

1. Clone the repository
   ```bash
   git clone https://github.com/vishalreddy20/itzfizz-hero-scroll-animation.git
   cd itzfizz-hero-scroll-animation-main
   ```

2. Install dependencies
   ```bash
   npm install
   ```

3. Run development server
   ```bash
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000) to see the result.

4. Build for production
   ```bash
   npm run build
   ```

### Test Production Build Locally
```bash
npm run build
npm run output-standalone  # Or manually copy from out/ for static export
npx serve -s out           # Serve static export locally
```

## 📦 Build & Deployment

### Production Build
```bash
npm run build
```

The build creates a static export in the `out/` directory (4 pages, ~47KB total).

### Netlify Deployment
[![Deploy to Netlify](https://www.netlify.com/img/deploy/button.svg)](https://app.netlify.com/start/deploy?repository=https://github.com/vishalreddy20/itzfizz-hero-scroll-animation)

Or deploy manually:
```bash
npm run build
# Deploy the out/ directory via Netlify UI or CLI
```

**Netlify Configuration:** See `netlify.toml` for build settings (Node 20, publish dir: `out/`)

### GitHub Pages Deployment
1. Enable GitHub Actions in repository settings
2. Set Pages source to "GitHub Actions" under Settings → Pages
3. Workflow automatically deploys on push to main branch

**Deploy URL:** `https://<username>.github.io/itzfizz-hero-scroll-animation`

See `.github/workflows/deploy.yml` for workflow configuration.

### Vercel Deployment
```bash
vercel deploy
```

Or connect repository directly in Vercel dashboa rd – automatic deploys on push.

## 📁 Project Structure

```
itzfizz-hero-scroll-animation-main/
├── app/
│   ├── layout.js           # Root layout, Google Fonts config
│   ├── page.js             # Main page wrapper
│   └── globals.css         # Global styles, Tailwind, CSS variables
├── components/
│   └── HeroSection.js      # Main hero section with GSAP animations (377 lines)
├── public/                 # Static assets
├── out/                    # Static export (generated on build)
├── next.config.js          # Next.js config (static export settings)
├── tailwind.config.js      # Tailwind CSS configuration
├── postcss.config.js       # PostCSS + Autoprefixer
├── netlify.toml            # Netlify deployment config
├── package.json            # Dependencies and scripts
└── README.md               # This file
```

## 🎨 Customization

### Change Color Scheme
Edit CSS variables in `app/globals.css`:
```css
:root {
  --accent: #e8ff00;        /* Yellow accent glow */
  --bg: #0a0a0a;            /* Near-black background */
  --text: #f0f0f0;           /* Off-white text */
  --muted: #444;             /* Muted gray */
}
```

### Modify Animation Timing
Edit duration and delay in `components/HeroSection.js`:
```javascript
// Headline animation – currently 0.3s per letter with 120ms stagger
gsap.from(letters, {
  duration: 0.3,
  delay: gsap.utils.unitize(i => i * 0.12),  // Change 0.12 for stagger timing
  opacity: 0,
  y: 60
});
```

### Adjust Font Styles
- Google Fonts loaded in `app/layout.js` (Bebas Neue, Space Mono)
- Tailwind classes use `font-bebas` and `font-space`
- Edit `tailwind.config.js` to add or remove fonts

### Customize Stats Section
Edit stats data directly in `components/HeroSection.js`:
```javascript
const stats = [
  { number: "500+", label: "Happy Clients" },
  { number: "1000+", label: "Projects Done" },
  // Add more stats...
];
```

## ⚡ Performance Metrics

### Build Output
- Total bundle: ~47 KB
- First Load JS: ~87 KB (shared chunks)
- Standalone modules: Optimized for static export
- Images: Optimized by Next.js (if added)

### Lighthouse Scores (Development)
- Performance: Excellent (smooth 60fps scroll animations)
- Accessibility: Good (semantic HTML, ARIA labels)
- Best Practices: Passed
- SEO: Optimized (responsive, meta tags)

### Optimizations Applied
- ✅ CSS-in-JS for hover states (instead of inline handlers)
- ✅ Ref-based GSAP selections (avoids querying DOM repeatedly)
- ✅ Conditional animation triggers (prevent null reference errors)
- ✅ Bootstrap grid + Tailwind (no layout shift)
- ✅ Grain texture as CSS (no extra images)
- ✅ Google Fonts optimized loading

## 🛠️ Technologies

### Core Framework
- **Next.js 14.2.3** – React meta-framework with static export
- **React 18** – UI component library

### Animation & Interactivity
- **GSAP 3.12.5** – Professional animation library
- **ScrollTrigger** – GSAP plugin for scroll-driven animations

### Styling
- **Tailwind CSS 3.4.3** – Utility-first CSS framework
- **Bootstrap 5.3.8** – Responsive grid system
- **PostCSS** – CSS tooling (Autoprefixer)
- **Google Fonts** – Bebas Neue, Space Mono

### Build & Deployment
- **Node.js 20** – JavaScript runtime
- **npm** – Package manager
- **GitHub Actions** – CI/CD automation
- **GitHub Pages** – Hosting
- **Netlify** – Alternative hosting

### Code Quality
- **ESLint** – JavaScript linting (configured)
- **Prettier** – Code formatting (optional)

## 🐛 Troubleshooting

### "Module not found: Can't resolve 'gsap'"
```bash
npm install gsap
```

### Build fails with "ScrollTrigger is undefined"
Ensure GSAP imports are correct in `HeroSection.js`:
```javascript
import gsap from "gsap";
import { ScrollTrigger } from "gsap/dist/ScrollTrigger";
gsap.registerPlugin(ScrollTrigger);
```

### Animations not triggering
- Check browser DevTools console for errors
- Verify refs are not null: `console.log(headlineRef.current)`
- Ensure ScrollTrigger plugin is registered
- Check scroll container: should be `window` not a fixed div

### Netlify deploy fails
- Ensure `netlify.toml` exists with correct node version (20)
- Check GitHub Actions logs for build errors
- Verify `out/` directory created locally: `npm run build && ls out/`

### GitHub Pages shows 404
- Enable GitHub Pages: Settings → Pages → Source: "GitHub Actions"
- Rerun workflow: Actions → Deploy → Re-run jobs
- Wait 2-3 minutes for deployment
- Check URL: `https://<username>.github.io/itzfizz-hero-scroll-animation`

## 📎 WordPress Integration

A WordPress theme template is included at `wordpress/hero-section-template.php`. This provides a PHP equivalent of the React HeroSection component for WordPress integration.

To use in WordPress:
1. Copy the PHP template to your WordPress theme directory
2. Update font URLs and paths as needed
3. Include GSAP via CDN in your theme's `functions.php`
4. Enqueue the component styles

## 📝 Assignment Info

**Project:** Itzfizz Hero Scroll Animation  
**Created:** 2024  
**Framework:** Next.js 14 with React 18  
**Deployment:** GitHub Pages, Netlify, Vercel  
**License:** MIT (or specify your license)

---

**Maintenance:** To keep animations smooth, periodically review GSAP ScrollTrigger documentation for new features and best practices.

**Questions?** Create an issue on GitHub or review the code comments in `components/HeroSection.js`.
