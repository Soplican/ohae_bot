
function initRoleSelector(roles, containerId) {

    let selected = [];

    const container = document.getElementById(containerId);

    container.innerHTML = `
        <div class="role-select">
            <input class="role-search" placeholder="Поиск роли">
            <div class="role-dropdown"></div>
            <div class="role-tags"></div>
        </div>
    `;

    const search = container.querySelector(".role-search");
    const dropdown = container.querySelector(".role-dropdown");
    const tags = container.querySelector(".role-tags");

    function renderDropdown(filter="") {
        dropdown.innerHTML = "";

        roles
            .filter(r => r.toLowerCase().includes(filter.toLowerCase()))
            .forEach(role => {

                const checked = selected.includes(role);

                const div = document.createElement("div");
                div.className = "role-option";

                div.innerHTML = `
                    <input type="checkbox" ${checked ? "checked" : ""}>
                    ${role}
                `;

                div.onclick = () => toggle(role);
                dropdown.appendChild(div);
            });
    }

    function toggle(role) {
        if(selected.includes(role)) {
            selected = selected.filter(r => r !== role);
        } else {
            selected.push(role);
        }
        renderDropdown(search.value);
        renderTags();
    }

    function renderTags() {
        tags.innerHTML = "";
        selected.forEach(role => {
            const tag = document.createElement("div");
            tag.className = "role-tag";
            tag.innerText = role;
            tag.onclick = () => toggle(role);
            tags.appendChild(tag);
        });
    }

    search.onfocus = () => dropdown.style.display = "block";
    search.oninput = () => renderDropdown(search.value);

    document.addEventListener("click", e => {
        if (!container.contains(e.target)) {
            dropdown.style.display = "none";
        }
    });

    renderDropdown();
}
