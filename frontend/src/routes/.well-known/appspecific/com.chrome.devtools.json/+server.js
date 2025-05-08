/** @type {import('@sveltejs/kit').RequestHandler} */
export function GET() {
  return new Response(JSON.stringify({}), {
    headers: {
      'Content-Type': 'application/json'
    }
  });
} 