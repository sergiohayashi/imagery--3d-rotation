// config.js
console.log("REACT_APP_VERSION", process.env?.REACT_APP_VERSION);
const config = {
    is_partner: true,
    apiUrl: 'http://localhost:8000', // Local API URL
    frontendUrl: 'https://localhost:3003', // Local API URL
}
config['msal-scope'] = ["user.read"]
config.is_dev = process.env.NODE_ENV !== 'production'
window._config = config;

export default config;
