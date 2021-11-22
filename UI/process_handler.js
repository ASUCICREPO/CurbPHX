const generateUUID = () => {
    let
        d = new Date().getTime(),
        d2 = (performance && performance.now && (performance.now() * 1000)) || 0;
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        let r = Math.random() * 16;
        if (d > 0) {
            r = (d + r) % 16 | 0;
            d = Math.floor(d / 16);
        } else {
            r = (d2 + r) % 16 | 0;
            d2 = Math.floor(d2 / 16);
        }
        return (c == 'x' ? r : (r & 0x7 | 0x8)).toString(16);
    });
};

function triggerLambda() {
    var s3 = document.getElementById('S3');
    var xml = document.getElementById('xml');
    if (s3.value == "" || xml.value == "") {
        alert("A field is empty");
        // window.location.href = ("page4.html");
    } else {
        window.job_id = generateUUID()

        // toggle the spinner
        let spinner = document.getElementsByClassName('spinner').item(0);
        spinner.style.display = 'block';

        // fetch("https://0w92hvwoaj.execute-api.us-east-1.amazonaws.com/Executed", requestOptions)
        fetch(`https://j0i8lxa0d9.execute-api.us-east-1.amazonaws.com/trigger-eagle-view-process?job_id=${window.job_id}&s3=${s3.value}&xml=${xml.value}`)
            .then(response => {
                console.dir(response);
                return response.json()
            })
            .then(res => {
                showLogs();
                trackProgress(res);
            })
            .catch(error => {
                hideSpinner();
                showLogs();
                console.error(error);
                handleError(error.message);
            })
    }
}

function hideSpinner() {
    let spinner = document.getElementsByClassName('spinner').item(0);
    spinner.style.display = 'none';
}

// https://0w92hvwoaj.execute-api.us-east-1.amazonaws.com/Executed
// make an api call every 10 secs until hundred percent
const timer = 10;
const milliseconds = 1000;
// change this when shapefile lambda is added
const max_messages = 30;
const final_message_keyword = 'Process Ended!';

const class_list_info = 'list-group-item list-group-item-info';
const class_list_danger = 'list-group-item list-group-item-danger';
const class_list_success = 'list-group-item list-group-item-success';

const KML = 'as_lines_color.kml'
const SHP = 'shp_arcgis.zip'

var last_length = 0

// hide the submit form and show the logs section
function showLogs() {
    let submitForm = document.getElementById('process-start-form')
    let processLogs = document.getElementById('process-logs')

    submitForm.style.display = 'none';
    processLogs.style.display = 'flex';

    // disable the next button
    let nextButton = document.getElementById('nextButton');
    nextButton.disabled = true;

    // update the logs
    let processListGroup = document.getElementById('process-list-group')
    let firstLog = document.createElement('li');
    firstLog.className = class_list_info;
    firstLog.innerHTML = 'Attempting to start the process...'
    processListGroup.append(firstLog);
}

function trackProgress(result) {
    hideSpinner();
    console.dir(result);


    if (result.errorType !== undefined) {
        handleError(`${result.errorType}: ${result.errorMessage}`);
    } else {
        // start the process
        queryProgress();
    }
}

// this will trigger after 'timer' seconds 
function startTimeout() {
    console.log('starting timeout')
    setTimeout(queryProgress, timer * milliseconds)
}

// function responsible to make the api call to the progress endpoint
function queryProgress() {
    console.log('querying process now')
    fetch("https://g4tk0vopw4.execute-api.us-east-1.amazonaws.com/status?job_id=" + window.job_id)
        .then(response => response.json())
        .then(res => handleResult(res))
        .catch(error => {
            console.error(error);
            handleError(error.message);
        })
}

function handleError(errorMessage) {
    console.log('handling error: ' + errorMessage)
    let progressBar = document.getElementById('process-bar')
    progressBar.classList.add('bg-danger')

    // update the logs
    let processListGroup = document.getElementById('process-list-group')
    let firstLog = document.createElement('li');
    firstLog.className = class_list_danger;
    firstLog.innerHTML = errorMessage;
    processListGroup.append(firstLog);

    let processLogsElem = document.getElementById('process-logs')
    processLogsElem.scrollTop = processLogsElem.scrollHeight;
}

// make all changes to the front end and the recall startTimeout
// until final_message_keyword is found!
function handleResult(result) {
    if (result.messages === undefined || result.messages.length == 0) {
        console.log('Empty messages', result);
        startTimeout();
        return
    }

    console.log(`there are ${result.messages.length} messages for job_id ${window.job_id}`);
    console.dir(result);

    let length = result.messages.length;

    percentage = Math.min(99, Math.ceil(length / max_messages * 100))

    // update progress bar percentage
    let progressBar = document.getElementById('process-bar')
    progressBar.setAttribute('style', `width:${percentage}%`);
    progressBar.innerHTML = `${percentage}%`

    // loop is skipped if length and last_length are the same
    for (i = last_length; i < length; i++) {

        message = result.messages[i];

        // update the logs
        let processListGroup = document.getElementById('process-list-group')
        let nextLog = document.createElement('li');
        let className = class_list_info
        if (result.hasError || message.includes(final_message_keyword)) {
            className = message.includes(final_message_keyword) ? class_list_success : class_list_danger;
            percentage = 100
            progressBar.setAttribute('style', `width:${percentage}%`);
            progressBar.innerHTML = `${percentage}%`
        }
        nextLog.className = className;
        nextLog.innerHTML = message;
        processListGroup.append(nextLog);

        let processLogsElem = document.getElementById('process-logs')
        processLogsElem.scrollTop = processLogsElem.scrollHeight;

        last_length = i + 1
        console.log('percentage: ' + percentage);
    }
    if (percentage < 100) {
        startTimeout();
    } else {
        console.dir(result);
        let nextButton = document.getElementById('nextButton');
        nextButton.disabled = false;

        // add shapefile signed url to cookies
        if (result["shpfilepaths"] !== undefined) {
            signed_uris = result["shpfilepaths"]
            for (let i = 0; i < signed_uris.length; i++) {
                if (signed_uris[i].includes(KML)) {
                    // only valid for one hour
                    setCookie(KML, signed_uris[i], 1 / 24)
                } else if (signed_uris[i].includes(SHP)) {
                    setCookie(SHP, signed_uris[i], 1 / 24)
                } else {
                    console.warn("some other link " + signed_uris[i])
                }
            }
        }
    }
}

function removeAllChildNodes(parent) {
    while (parent.firstChild) {
        parent.removeChild(parent.firstChild);
    }
}

function goBack() {
    // hide the submit form and show the logs section
    let submitForm = document.getElementById('process-start-form')
    let processLogs = document.getElementById('process-logs')
    submitForm.style.display = 'block';
    processLogs.style.display = 'none';

    // reset progress bar
    let progressBar = document.getElementById('process-bar')
    progressBar.setAttribute('style', `width:${2}%`);
    progressBar.innerHTML = `0%`

    // reset log messages
    let processListGroup = document.getElementById('process-list-group')
    removeAllChildNodes(processListGroup);
}

function goNext() {
    window.location.href = ("page4.html");
}

function setCookie(name, value, days) {
    var expires = "";
    if (days) {
        var date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "") + expires + "; path=/";
}

function eraseCookie(name) {
    document.cookie = name + '=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;';
}