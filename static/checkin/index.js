const event = prompt("Please enter run name (saturday/sunday):");
const wait = 6;

let qrScanner;

function showPage(id) {
    document.getElementById("home").style.display = "none";
    document.getElementById("success").style.display = "none";
    document.getElementById("failure").style.display = "none";
    document.getElementById("load").style.display = "none";

    document.getElementById(id).style.display = "block";
}

function scannedCode(result) {
    // Enter load mode...
    qrScanner.stop();
    showPage("load");

    // Send to backend
    fetch(`/plinko/checkin?member_id=${result.data}&run=${event.toLowerCase()}`).then(evt => {
        // Serialize JSON
        return evt.json()
    }).then(json => {
        if (json.success === false) {
            document.getElementById("err_msg").innerText = json.msg;
            showPage("failure");

            // `wait` second timeout.
            setTimeout(() => {
                showPage("home");
                qrScanner.start();
            }, wait * 1000);
        } else {
            // Show result to user.
            document.getElementById("name").innerText = `Welcome, ${json.user.first_name}!`;
            document.getElementById("flavor").innerHTML = `<h2>You are on Team ${json.user.team_number}.<h2><br>
        <h3>Please head to ENG1-188 by following the <em class="blue">blue</em> signs.</h3>
        <h3>Your table will have a <em>Team ${json.user.team_number}</em> sign on it.</h3>
        `;
            showPage("success");

            // `wait` second timeout.
            setTimeout(() => {
                showPage("home");
                qrScanner.start();
            }, wait * 1000);
        }
    }).catch(evt => {
        document.getElementById("err_msg").innerText = "Invalid QR code.";
        showPage("failure");

        setTimeout(() => {
            showPage("home");
            qrScanner.start();
        }, wait * 1000);
    })
}

window.onload = () => {
    document.querySelector("b").innerText = event;

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

    qrScanner.start();
}