/**
 * Public mock-data demo: browser requests never need a staff session.
 * samoraRequest attaches the private backend API key on the server.
 */
export async function requireExecutiveAccess(_method="GET"){
 return {response:null,user:null,accessToken:null,role:"demo"};
}
