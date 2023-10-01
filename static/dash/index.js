const event = prompt("Please enter run name (saturday/sunday):");

function populate_team(num, team) {
    let out = `<div class="team"><span class="team_number">${num + 1}</span>`;

    // check-in rate calculator
    let total = team.length;
    let checkin = 0;
    for (let i = 0; i < team.length; i++) {
        if (team[i].checked_in)
            checkin++;
    }

    for (let i = 0; i < checkin; i++) {
        out += `<span class="yes">O</span>`;
    }
    for (let i = 0; i < total - checkin; i++) {
        out += `<span class="no">X</span>`;
    }

    out += `</div>`;

    return out;
}


function populate_column(teams, min, max) {
    let out = "";
    for (let i = min; i < max; i++) {
        if (typeof teams[i] !== "undefined") {
            out += populate_team(i, teams[i]);
        }
    }
    return out;
}


function populate_page(teams) {
    let out = `<div id="room_green" class="room">
        <h2 class="team green">ENG1-187</h2>
        ${populate_column(teams, 0, 7)}
    </div>
    <div id="room_purple" class="room">
        <h2 class="team purple">ENG1-188</h2>
        ${populate_column(teams, 7, 15)}
    </div>`;

    // Yes, I know this is unsafe.
    document.getElementById("room_el").innerHTML = out;
}

function update() {
    fetch("/admin/list").then(data => {
        return data.json()
    }).then(json => {
        const data = json.data;

        // Find number of teams
        let team_count = -1;
        for (let i = 0; i < data.length; i++) {
            const user = data[i];

            if (user.team_number > team_count)
                team_count = user.team_number;
        }

        // Prepare team-info array for filling
        let teams = [];
        for (let i = 0; i < team_count; i++) {
            teams.push([]);
        }
        
        // Populate team-info array
        for (let i = 0; i < data.length; i++) {
            const user = data[i];

            if (user.waitlist === 1 && user.assigned_run.toLowerCase() === event.toLowerCase()) {
                teams[Number(user.team_number) - 1].push(user);
            }
        }

        populate_page(teams);
    })
}

window.onload = () => {
    document.querySelector("b").innerText = event;

    setInterval(() => {
        // update();
    }, 15 * 1000); // update every 15 seconds
    update();
}