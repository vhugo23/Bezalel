import { readFile, writeFile, mkdir } from 'node:fs/promises';
import openapiTS, { astToString } from 'openapi-typescript';
const document = JSON.parse(await readFile(new URL('../openapi.json', import.meta.url), 'utf8'));
const dir = new URL('../src/api/', import.meta.url);
await mkdir(dir, { recursive: true });
await writeFile(new URL('types.ts', dir), astToString(await openapiTS(document)));
function schema(s) {
  if (s.$ref) return `z.lazy(() => schemas[${JSON.stringify(s.$ref.split('/').pop())}])`;
  if (s.const !== undefined) return `z.literal(${JSON.stringify(s.const)})`;
  if (s.enum) return `z.union([${s.enum.map(v=>`z.literal(${JSON.stringify(v)})`).join(',')}])`;
  if (s.anyOf || s.oneOf) return `z.union([${(s.anyOf||s.oneOf).map(schema).join(',')}])`;
  if (s.type === 'null') return 'z.null()';
  if (s.type === 'array') return `z.array(${schema(s.items||{})})${s.minItems?`.min(${s.minItems})`:''}${s.maxItems?`.max(${s.maxItems})`:''}`;
  if (s.type === 'object' || s.properties) {
    if (!s.properties) return `z.record(z.string(),${s.additionalProperties && typeof s.additionalProperties==='object'?schema(s.additionalProperties):'z.unknown()'})`;
    return `z.object({${Object.entries(s.properties).map(([k,v])=>`${JSON.stringify(k)}:${schema(v)}${s.required?.includes(k)?'':'.optional()'}`).join(',')}})${s.additionalProperties === false?'.strict()':'.passthrough()'}`;
  }
  if (s.type === 'string') return `z.string()${s.minLength?`.min(${s.minLength})`:''}${s.maxLength?`.max(${s.maxLength})`:''}`;
  if (s.type === 'boolean') return 'z.boolean()';
  if (s.type === 'integer' || s.type === 'number') return `z.number()${s.type==='integer'?'.int()':''}${s.minimum!==undefined?`.min(${s.minimum})`:''}${s.maximum!==undefined?`.max(${s.maximum})`:''}`;
  return 'z.unknown()';
}
await writeFile(new URL('schemas.ts',dir),`// Generated from FastAPI OpenAPI. Run npm run api:generate.\nimport { z } from 'zod';\nexport const schemas: Record<string,z.ZodType> = {\n${Object.entries(document.components.schemas).map(([k,v])=>`${JSON.stringify(k)}:${schema(v)}`).join(',\n')}\n};\n`);
console.log('Generated TypeScript and Zod schemas from FastAPI OpenAPI.');
