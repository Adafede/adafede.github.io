// The site ships one script: addEventListener replaces every inline event
// handler so nothing has to appear in the strict-dynamic script-src-attr list.
// Both forms are pure-CSS/no-op forms — their only job is to hold controls, so
// submitting them would do nothing but reload the page.
document
  .querySelectorAll("form.theme-switch-form, form.tag-filter__form")
  .forEach((form) => {
    form.addEventListener("submit", (event) => event.preventDefault());
  });
