let userDict = {};
let userList;
let qrScanner;

function load() {
    let valueNames = ["Name", "Status", "Team Number", "Assigned Run", "Discord", "Email", "Details"];
    let valueItems = "<tr>";
    let valueHeader = "<tr>";
    for (let i = 0; i < valueNames.length; i++) {
        valueItems += `<td class="${valueNames[i].toLowerCase()}"></td>`;
        valueHeader += `<td><button class="sort totally_text" data-sort="${valueNames[i].toLowerCase().replaceAll(' ', '')}">${valueNames[i]}</button></td>`
        valueNames[i] = valueNames[i].toLowerCase().replaceAll(' ', '');
    }
    valueItems += "</tr>";
    valueHeader += "</tr>";

    document.querySelector("thead").innerHTML = valueHeader;

    const options = {
        valueNames: valueNames,
        item: valueItems,
        searchColumns: ["name", "nid", "teamnumber", "assignedrun", "discord", "email", "status"]
    };

    let members = [];
    let count_competing = 0;
    let count_waitlist = 0;
    let count_all = 0;

    fetch("/admin/list").then(data => {
        return data.json();
    }).then(data2 => {
        data2 = data2.data;
        for (let i = 0; i < data2.length; i++) {
            member = data2[i];

            let userStatus = userStatusString(member);
            let userEntry = {
                "id": sanitizeHTML(member.id).replaceAll("&#45;", "-"),
                "name": sanitizeHTML(member.first_name + " " + member.last_name),
                "teamnumber": sanitizeHTML(member.team_number),
                "assignedrun": sanitizeHTML(member.assigned_run),
                "status": userStatus,
                "discord": "@" + sanitizeHTML(member.discord.username),
                "email": sanitizeHTML(member.email),
                "nid": sanitizeHTML(member.nid),
                "experience": sanitizeHTML(member.experience),
                "details": `<button class="searchbtn btn" onclick="showUser('${sickoModeSanitize(member.id)}')">Details</a>`
            }

            count_all++;
            if (member.waitlist == 1)
                count_competing++;
            else if (member.waitlist > 1)
                count_waitlist++;

            members.push(userEntry);

            member.name = member.first_name + " " + member.last_name;
            member.username = "@" + member.discord.username;
            member.pfp = member.discord.avatar;
            member.status = userStatus;
            userDict[sickoModeSanitize(member.id)] = member;
        }

        userList = new List('users', options, members);

        document.querySelector(".right").innerHTML += `<br>${count_competing} competing, ${count_waitlist} waitlisted, ${count_all} total`;
    })
}

function userStatusString(member) {
    const status = member.waitlist;

    if (status == 1) {
        return "Registered";
    }

    if (status == 0) {
        return "Not Registered"
    }

    if (status > 1) {
        return "Waitlisted";
    }

    return "Not Registered"; // Unactivated account
}

// Sanitizes any non-alphanum.
function sickoModeSanitize(val) {
    return val.replaceAll(/[^\w\-]/g, "");
}

/**
 * Sanitize and encode all HTML in a user-submitted string
 * https://portswigger.net/web-security/cross-site-scripting/preventing
 * Needed because our table-searching library is circumstantially vulnerable to XSS.
 * @param  {String} str  The user-submitted string
 * @return {String} str  The sanitized string
 */
const sanitizeHTML = (data) => {
    if (data) {
        data = data.toString();
        return data.replace(/[^\w. ]/gi, function (c) {
            return '&#' + c.charCodeAt(0) + ';';
        });
    } else {
        return "";
    }
};

function showTable() {
    qrScanner.stop();
    
    document.getElementById("user").style.display = "none";
    document.getElementById("scanner").style.display = "none";
    document.getElementById("users").style.display = "block";
}

function showQR() {
    qrScanner.start();

    const camLS = localStorage.getItem("adminCam");
    if (camLS && typeof camLS !== "undefined") {
        qrScanner.setCamera(camLS);
    }
    
    document.getElementById("user").style.display = "none";
    document.getElementById("users").style.display = "none";
    document.getElementById("scanner").style.display = "block";
}

function showUser(userId) {
    const user = userDict[userId]

    // Header details
    document.getElementById("pfp").src = user.pfp;
    document.getElementById("name").innerText = user.name;
    document.getElementById("discord").innerText = user.username;

    // Statuses
    document.getElementById("statusColor").style.color = user.waitlist === 1 ? "#51cd7f" : "#cf565f";
    
    document.getElementById("status").innerText = user.status;
    document.getElementById("shirt_status").innerText = user.did_get_shirt ? "Claimed" : `Unclaimed`

    // Identifiers
    document.getElementById("id").innerText = user.id;
    document.getElementById("hackucf_id").innerText = user.hackucf_id;
    document.getElementById("email").innerText = user.email;

    // Demography
    document.getElementById("comp_day").innerText = user.assigned_run ? user.assigned_run : "Unassigned: Prefers " + user.availability.replace(" works.", "");
    document.getElementById("team_number").innerText = user.team_number ? user.team_number : "Unassigned";
    document.getElementById("team_name").innerText = user.team_name ? user.team_name : "Solo";
    document.getElementById("experience").innerText = user.experience ? user.experience : "Not Collected";



    document.getElementById("user_json").innerText = JSON.stringify(user, "\t", "\t")

    // Set buttons up
    document.getElementById("claimShirt").onclick = (evt) => {
        editUser({
            "id": user.id,
            "did_get_shirt": true
        })
    };
    document.getElementById("claimShirt").style.display = user.did_get_shirt ? "none" : "inline-block";

    document.getElementById("setAdmin").onclick = (evt) => {
        editUser({
            "id": user.id,
            "sudo": !user.sudo
        })
    };
    document.getElementById("adminLabel").innerText = user.sudo ? "Revoke Admin" : "Promote to Admin";

    document.getElementById("sendMessage").onclick = (evt) => {
        const message = prompt("Please enter message to send to user:");
        sendDiscordDM(user.id, message);
    }

    // Set page visibilities
    document.getElementById("users").style.display = "none";
    document.getElementById("scanner").style.display = "none";
    document.getElementById("user").style.display = "block";
}

function editUser(payload) {
    const options = {
        method: "POST",
        body: JSON.stringify(payload),
        headers: {
            "Content-Type": "application/json"
        }
    }
    const user_id = payload.id;
    fetch("/admin/get", options).then(data => {
        return data.json();
    }).then(data2 => {
        // Update user data.
        let member = data2.data;

        member.name = member.first_name + " " + member.last_name;
        member.username = "@" + member.discord.username;
        member.pfp = member.discord.avatar;
        member.status = userStatusString(member);

        userDict[user_id] = member;
        showUser(user_id);
    })
}

function sendDiscordDM(user_id, message) {
    const payload = {
        "msg": message
    }
    const options = {
        method: "POST",
        body: JSON.stringify(payload),
        headers: {
            "Content-Type": "application/json"
        }
    }
    fetch("/admin/message?member_id=" + user_id, options).then(data => {
        return data.json();
    }).then(data2 => {
        alert(data2.msg);
    })
}

function verifyUser(user_id) {
    fetch("/admin/refresh?member_id=" + user_id).then(data => {
        return data.json();
    }).then(data2 => {
        // Update user data.
        let member = data2.data;

        member.name = member.first_name + " " + member.last_name;
        member.username = "@" + member.discord.username;
        member.pfp = member.discord.avatar;
        member.status = userStatusString(member);

        userDict[user_id] = member;
        showUser(user_id);
    })
}

function inviteToInfra(user_id) {
    fetch("/admin/infra?member_id=" + user_id).then(data => {
        return data.json();
    }).then(resp => {
        // Update user data.
        alert(`The user has been provisioned and a Discord message with credentials sent!

Username: ${resp.username}
Password: ${resp.password}`);

        userDict[user_id].infra_email = resp.username;
        showUser(user_id);
    })
}

function logoff() {
    document.cookie = 'token=; Max-Age=0; path=/; domain=' + location.hostname;
    window.location.href = "/logout";
}

function changeCamera() {
    QrScanner.listCameras().then(evt => {
        const cameras = evt;
        let camArray = [];
        let camString = "Please enter a camera number:";
        for (let i = 0; i < cameras.length; i++) {
            camString += `\n${i}: ${cameras[i].label}`;
            camArray.push(cameras[i].id);
        }
        let camSelect = prompt(camString);

        localStorage.setItem("adminCam", camArray[camSelect]);
        qrScanner.setCamera(camArray[camSelect]);
    });
}

function scannedCode(result) {
    // Enter load mode...
    qrScanner.stop();

    showUser(result.data);
}

function filter(showOnlyActiveUsers) {
    // showActiveUsers == true -> only active shown
    // showActiveUsers == false -> only inactive shown
    userList.filter((item) => {
        let activeOrInactive = item.values().is_full_member;
        if (!showOnlyActiveUsers) {
            activeOrInactive = !activeOrInactive
        }
        return activeOrInactive;
    });

    document.getElementById("activeFilter").innerText = showOnlyActiveUsers ? "Active" : "Inactive"
    document.getElementById("activeFilter").onclick = (evt) => {
        filter(!showOnlyActiveUsers);
    }
}

function mentorFilter(isMentorMode) {
    // isMentorMode == true -> show those in mentor program
    // isMentorMode == false -> show all
    userList.filter((item) => {
        let activeOrInactive = (item.values().mentee && item.values().mentee !== "Not Mentee");
        if (!isMentorMode) {
            activeOrInactive = true;
        }
        return activeOrInactive;
    });

    document.getElementById("menteeFilter").innerText = isMentorMode ? "Mentees" : "All Mentee"
    document.getElementById("menteeFilter").onclick = (evt) => {
        mentorFilter(!isMentorMode);
    }
}

window.onload = evt => {
    load();

    // Prep QR library
    const videoElem = document.querySelector("video");
    qrScanner = new QrScanner(
        videoElem,
        scannedCode,
        {
            maxScansPerSecond: 10,
            highlightScanRegion: true,
            returnDetailedScanResult: true 
        },
    );

    // Default behavior
    document.getElementById("goBackBtn").onclick = (evt) => {
        showTable();
    }

    // Turn ON the QR Scanner mode.
    document.getElementById("scannerOn").onclick = (evt) => {
        showQR();

        document.getElementById("goBackBtn").onclick = (evt) => {
            showQR();
        }
    }

    document.getElementById("scannerOff").onclick = (evt) => {
        showTable();

        document.getElementById("goBackBtn").onclick = (evt) => {
            showTable();
        }
    }

    document.getElementById("changeCamera").onclick = (evt) => {
        changeCamera();
    }

    // Filter buttons
    document.getElementById("activeFilter").onclick = (evt) => {
        filter(true);
    }

    document.getElementById("menteeFilter").onclick = (evt) => {
        mentorFilter(true);
    }
}