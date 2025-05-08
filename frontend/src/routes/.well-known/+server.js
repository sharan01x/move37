/** @type {import('@sveltejs/kit').RequestHandler} */
export function GET({ url }) {
  // Catch-all handler for .well-known requests
  return new Response(JSON.stringify({}), {
    headers: {
      'Content-Type': 'application/json'
    }
  });
} 