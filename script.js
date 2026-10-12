(function () {
  var nav = document.querySelector(".nav");
  var toggle = document.querySelector(".nav__toggle");
  var menu = document.getElementById("menu");

  // Sticky nav background on scroll
  function onScroll() {
    nav.classList.toggle("is-scrolled", window.scrollY > 40);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // Mobile menu
  toggle.addEventListener("click", function () {
    var open = nav.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", String(open));
  });
  menu.addEventListener("click", function (e) {
    if (e.target.tagName === "A") {
      nav.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
    }
  });

  // Reveal on scroll
  var items = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15 });
    items.forEach(function (el) { io.observe(el); });
  } else {
    items.forEach(function (el) { el.classList.add("is-visible"); });
  }

  // Lead form -> WhatsApp
  var form = document.getElementById("lead-form");
  var msg = form.querySelector(".form__msg");
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var name = form.name.value.trim();
    var phone = form.phone.value.trim();
    if (!name || !/^[0-9+\-\s]{9,}$/.test(phone)) {
      msg.textContent = "נא למלא שם ומספר טלפון תקין.";
      return;
    }
    msg.textContent = "";
    var text = "היי, אשמח לפרטים על אימון ניסיון.\nשם: " + name + "\nטלפון: " + phone + "\nקבוצה: " + form.group.value;
    window.open("https://wa.me/972524890055?text=" + encodeURIComponent(text), "_blank", "noopener");
  });

  document.getElementById("year").textContent = new Date().getFullYear();
})();
