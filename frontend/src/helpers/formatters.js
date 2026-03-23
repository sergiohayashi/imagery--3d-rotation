export function formatDateMonthDay(date) {
    if (!date) return null;
    if (!(date instanceof Date)) {
        date = new Date(date);
    }
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0'); // Months are zero-based
    const day = String(date.getDate()).padStart(2, '0');

    return `${month}-${day}`;
}


export function simpleDateFormatter(input) {
    if (!input) return input;
    if (typeof input !== 'string') {
        return input;
    }
    const [date, timeWithMilliseconds] = input.split('T');
    const [year, month, day] = date.split('-');
    const [time] = timeWithMilliseconds.split('.');
    const [hour, minute] = time.split(':');

    return `${year}/${month}/${day} ${hour}:${minute}`;
}
