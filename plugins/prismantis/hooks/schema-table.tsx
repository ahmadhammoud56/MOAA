import { inlineText } from './markdown'
import type { TableCell, TableBlock } from './markdown'
import type { Theme } from './theme'

export type SchemaTable = 'off' | 'types' | 'keys' | 'full'

export type Schema = { types: number; keys: number }

const LABEL = /^(?:columns?|fields?)$/i

const TYPE = /^(?:data type|types?)$/i

const KEY = /^(?:keys?|constraints?|indexes?|indices?)$/i

type Family = 'text' | 'number' | 'bool' | 'time'

const FAMILIES: Partial<Record<string, Family>> = {}

for (const word of ['char', 'character', 'varchar', 'text', 'string', 'uuid', 'json', 'jsonb', 'blob', 'bytea', 'clob', 'enum', 'xml']) FAMILIES[word] = 'text'

for (const word of ['int', 'integer', 'smallint', 'bigint', 'tinyint', 'mediumint', 'decimal', 'numeric', 'float', 'double', 'real', 'serial', 'bigserial', 'smallserial', 'money', 'bit', 'year']) FAMILIES[word] = 'number'

for (const word of ['bool', 'boolean']) FAMILIES[word] = 'bool'

for (const word of ['date', 'time', 'datetime', 'timestamp', 'timestamptz', 'timetz', 'interval']) FAMILIES[word] = 'time'

const FAMILY_TOKEN: Record<Family, 'codeString' | 'number' | 'emphasis' | 'link'> =
  { text: 'codeString', number: 'number', bool: 'emphasis', time: 'link' }

type Key = 'primary' | 'foreign' | 'limited'

const KEY_TOKEN: Record<Key, 'accent' | 'link' | 'codeComment'> = { primary: 'accent', foreign: 'link', limited: 'codeComment' }

const PRIMARY = /(?:^|\W)(?:pk|primary key)(?:\W|$)/i

const FOREIGN = /(?:^|\W)(?:fk|foreign key|references)(?:\W|$)/i

const LIMITED = /(?:^|\W)(?:unique|uq|idx|index)(?:\W|$)/i

const familyOf = (cell: TableCell): Family | undefined => {
  const word = inlineText(cell).trim().toLowerCase().match(/^[a-z]+/)?.[0]
  return word ? FAMILIES[word] : undefined
}

const keyOf = (cell: TableCell): Key | undefined => {
  const text = inlineText(cell).trim()
  if (PRIMARY.test(text)) return 'primary'
  if (FOREIGN.test(text)) return 'foreign'
  if (LIMITED.test(text)) return 'limited'
  return undefined
}

const columnOf = (block: TableBlock, names: RegExp): number =>
  block.header.findIndex(h => names.test(inlineText(h).trim()))

const keysOf = (block: TableBlock, keyed: number): number => {
  if (keyed >= 0) return keyed
  return block.header.findIndex((_, c) => block.rows.filter(row => keyOf(row[c]!)).length * 2 > block.rows.length)
}

export const schemaOf = (block: TableBlock, option: SchemaTable): Schema | undefined => {
  if (option === 'off' || block.rows.length < 2) return undefined
  const types = columnOf(block, TYPE)
  if (types < 0 || !block.header.some(h => LABEL.test(inlineText(h).trim()))) return undefined
  return { types: option === 'keys' ? -1 : types, keys: option === 'types' ? -1 : keysOf(block, columnOf(block, KEY)) }
}

export const schemaLook = (t: Theme, schema: Schema | undefined, c: number, cell: TableCell, plain: { color?: string } = {}): { color?: string } => {
  if (!schema) return plain
  if (c === schema.types) {
    const family = familyOf(cell)
    if (family) return { color: t[FAMILY_TOKEN[family]] }
  }
  if (c === schema.keys) {
    const key = keyOf(cell)
    if (key) return { color: t[KEY_TOKEN[key]] }
  }
  return plain
}
