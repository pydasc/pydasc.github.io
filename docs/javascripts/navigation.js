(() => {
  const drawer = document.querySelector("#__drawer");
  const control = document.querySelector("[data-dasc-drawer-control]");
  if (!(drawer instanceof HTMLInputElement) || !(control instanceof HTMLElement)) {
    return;
  }

  const syncState = () => {
    control.setAttribute("aria-expanded", String(drawer.checked));
    control.setAttribute(
      "aria-label",
      drawer.checked ? "Close documentation navigation" : "Open documentation navigation"
    );
  };

  control.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      // Material also handles Enter globally; keep one drawer activation.
      event.stopPropagation();
      control.click();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && drawer.checked) {
      drawer.checked = false;
      drawer.dispatchEvent(new Event("change", { bubbles: true }));
      control.focus();
    }
  });

  drawer.addEventListener("change", syncState);
  syncState();
})();
