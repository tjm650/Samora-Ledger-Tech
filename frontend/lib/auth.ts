// Temporary open-access mode. Restore Supabase user and staff-role validation
// before production use; the upstream Samora API key remains server-side.
export async function requireExecutiveAccess(){
 return {response:null,user:null};
}
