(function () {
  function ready(fn) {
    if (document.readyState !== "loading") {
      fn();
      return;
    }
    document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    var toggle = document.getElementById("mvMenuToggle");
    var drawer = document.getElementById("mvDrawer");
    var overlay = document.getElementById("mvDrawerOverlay");
    if (!toggle || !drawer || !overlay) return;

    function setOpen(open) {
      document.body.classList.toggle("mv-drawer-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    }

    toggle.addEventListener("click", function () {
      setOpen(!document.body.classList.contains("mv-drawer-open"));
    });

    overlay.addEventListener("click", function () {
      setOpen(false);
    });

    drawer.addEventListener("click", function (e) {
      var link = e.target.closest("a");
      if (!link) return;

      if (link.hasAttribute("data-logout")) {
        e.preventDefault();
        setOpen(false);
        try {
          localStorage.removeItem("mv_access_token");
          localStorage.removeItem("mv_last_login_email");
          sessionStorage.removeItem("mv_access_token");
        } catch (err) {}
        var page = (location.pathname.split("/").pop() || "ratings.html");
        location.replace("/auth.html?next=" + encodeURIComponent(page));
        return;
      }

      setOpen(false);
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") setOpen(false);
    });
  });
})();
