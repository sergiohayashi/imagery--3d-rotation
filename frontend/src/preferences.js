// function loadObject(name, _default) {
//     const json = localStorage.getItem(name)
//     try {
//         return json ? JSON.parse(json) : _default
//     } catch (error) {
//         return _default;
//     }
// }
//
// function saveObject(name, object) {
//     localStorage.setItem(name, JSON.stringify(object));
// }

export const reasoningEffortPreferenceKey = (name) => {
    return `reasoning_effort--${name}`;
}

export const keyForBookmarkedModels = "bookmarked_models";

export const keyFor = (model,option) => {
    return `${option}--${model}`;
}

export function addPreference(prefs, key, value)
{
    prefs[key] = value
}

export function deletePreference(prefs, key)
{
    delete prefs[key]
}

export function existPreference(prefs, key) {
    return key in prefs;
}

