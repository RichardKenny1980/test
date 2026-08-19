(function () {
  var seconds = parseInt(document.body.getAttribute("data-refresh-seconds"), 10) || 30;
  window.setTimeout(function () {
    window.location.reload();
  }, seconds * 1000);
})();
