// Hides events the moment they end, even if the nightly rebuild that removes
// them from the HTML hasn't run yet. Any element with data-event-end="<ISO
// date>" is hidden once that time has passed. Groups marked data-event-group
// hide when they have no events left; lists marked data-event-list reveal
// their data-events-empty message instead.
(function () {
  "use strict";
  var now = Date.now();
  var each = function (sel, fn) {
    Array.prototype.forEach.call(document.querySelectorAll(sel), fn);
  };
  var hasLiveEvent = function (el) {
    return !!el.querySelector("[data-event-end]:not([hidden])");
  };
  each("[data-event-end]", function (el) {
    var end = Date.parse(el.getAttribute("data-event-end"));
    if (!isNaN(end) && end <= now) el.hidden = true;
  });
  each("[data-event-group]", function (g) {
    if (!hasLiveEvent(g)) g.hidden = true;
  });
  each("[data-event-list]", function (list) {
    if (hasLiveEvent(list)) return;
    each("[data-events-empty]", function (msg) { msg.hidden = false; });
  });
})();
