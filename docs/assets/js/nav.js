document.addEventListener("DOMContentLoaded", function() {
    var navContainer = document.querySelector(".reversa-doc-nav");
    if (!navContainer && window.RV_DATA && window.RV_DATA.nav) {
        var header = document.querySelector("header");
        if (header) {
            navContainer = document.createElement("nav");
            navContainer.className = "reversa-doc-nav";
            header.appendChild(navContainer);
        }
    }
    if (navContainer && window.RV_DATA && window.RV_DATA.nav) {
        var html = "";
        var currentPath = window.location.pathname.split("/").pop() || "index.html";
        window.RV_DATA.nav.forEach(function(item) {
            var active = (currentPath === item.href) ? ' aria-current="page" class="active"' : '';
            html += '<a href="' + item.href + '" data-page-id="' + item.id + '"' + active + '>' + item.label + '</a> ';
        });
        navContainer.innerHTML = html;
    }
});
