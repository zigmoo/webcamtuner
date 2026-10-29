function keyFor(id, aliases) {
    for (var i = 0; i < aliases.length; i++)
        if (aliases[i].path === id && aliases[i].primary) return aliases[i].key
    return "device:" + id
}

function visibleInputs(inputs, aliases) {
    var result = []
    for (var i = 0; i < inputs.length; i++) {
        var known = false, primary = false
        for (var j = 0; j < aliases.length; j++) {
            if (aliases[j].path === String(inputs[i].id)) {
                known = true
                primary = primary || aliases[j].primary
            }
        }
        // Hide secondary UVC infrared/metadata endpoints from the normal webcam choice.
        if (!known || primary) result.push(inputs[i])
    }
    return result
}

function pick(inputs, aliases, lastKey, currentId, profileId, defaultId) {
    if (inputs.length === 0) return ""
    if (inputs.length === 1) return String(inputs[0].id)
    for (var i = 0; i < inputs.length; i++)
        if (String(inputs[i].id) === currentId) return currentId
    for (var j = 0; j < inputs.length; j++)
        if (keyFor(String(inputs[j].id), aliases) === lastKey) return String(inputs[j].id)
    for (var k = 0; k < inputs.length; k++)
        if (String(inputs[k].id) === profileId) return profileId
    for (var n = 0; n < inputs.length; n++)
        if (String(inputs[n].id) === defaultId) return defaultId
    return String(inputs[0].id)
}
