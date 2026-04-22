const header = document.querySelector(".site-header");
const mobileToggle = document.querySelector(".mobile-toggle");
const mobilePanel = document.querySelector(".mobile-panel");
const menuBackdrop = document.querySelector(".menu-backdrop");
const revealItems = document.querySelectorAll("[data-reveal]");
const yearTarget = document.getElementById("year");

const syncHeaderState = () => {
  if (!header) return;
  header.classList.toggle("is-scrolled", window.scrollY > 20);
};

const closeMenu = () => {
  if (!header || !mobileToggle || !mobilePanel) return;
  header.classList.remove("menu-open");
  document.body.classList.remove("menu-open");
  mobileToggle.setAttribute("aria-expanded", "false");
  if (menuBackdrop) menuBackdrop.hidden = true;
};

const openMenu = () => {
  if (!header || !mobileToggle || !mobilePanel) return;
  header.classList.add("menu-open");
  document.body.classList.add("menu-open");
  mobileToggle.setAttribute("aria-expanded", "true");
  if (menuBackdrop) menuBackdrop.hidden = false;
};

if (yearTarget) {
  yearTarget.textContent = String(new Date().getFullYear());
}

syncHeaderState();
window.addEventListener("scroll", syncHeaderState, { passive: true });

if (mobileToggle && mobilePanel && header) {
  mobileToggle.addEventListener("click", () => {
    const isOpen = header.classList.contains("menu-open");
    if (isOpen) {
      closeMenu();
    } else {
      openMenu();
    }
  });

  mobilePanel.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => closeMenu());
  });

  menuBackdrop?.addEventListener("click", () => closeMenu());

  window.addEventListener("resize", () => {
    if (window.innerWidth > 920) closeMenu();
  });

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeMenu();
  });
}

document.querySelectorAll(".placeholder-link").forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
  });
});

document.querySelectorAll("[data-marquee]").forEach((marquee) => {
  const group = marquee.querySelector(".marquee__group");
  if (!group) return;

  marquee.style.setProperty("--duration", marquee.dataset.duration || "36s");

  if (!marquee.dataset.cloned) {
    const clone = group.cloneNode(true);
    marquee.appendChild(clone);
    marquee.dataset.cloned = "true";
  }
});

if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    {
      threshold: 0.16,
      rootMargin: "0px 0px -6% 0px",
    },
  );

  revealItems.forEach((item) => observer.observe(item));
} else {
  revealItems.forEach((item) => item.classList.add("is-visible"));
}
