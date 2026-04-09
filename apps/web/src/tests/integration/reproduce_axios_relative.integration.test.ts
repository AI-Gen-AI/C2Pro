import { it, expect } from 'vitest';
import axios from 'axios';

it('reproduces axios relative URL issue', async () => {
  console.log('START TEST: axios with baseURL:', axios.defaults.baseURL);
  
  try {
    const res = await axios.get('/v1/test');
    console.log('Success (unexpected):', res.status);
    // If it succeeds, it means it's NOT throwing ERR_INVALID_URL
  } catch (err: any) {
    console.log('EXPECTED ERROR:', err.message);
    if (err.code) console.log('ERROR CODE:', err.code);
    return;
  }
  
  // If we reach here, it didn't throw. 
  // In Node, a relative URL with axios SHOULD throw if not intercepted or if baseURL is relative.
});
