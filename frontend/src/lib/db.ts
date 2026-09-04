import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

export interface Category {
  id: number;
  name: string;
}

export interface Brand {
  id: number;
  name: string;
  logo_filename?: string;
}

export interface Product {
  id: number;
  name: string;
  category_id: number;
  brand: string;
  unit: string;
  image_url: string;
  is_public: number;
  category_name?: string;
}

let db: Database.Database | null = null;

function getDb(): Database.Database | null {
  if (db) return db;
  try {
    const dbPath = path.resolve(process.cwd(), '../database.db');
    db = new Database(dbPath, { readonly: true });
    return db;
  } catch (error) {
    console.error('Failed to connect to the SQLite database:', error);
    return null;
  }
}

export function getCategories(): Category[] {
  const database = getDb();
  if (!database) return [];
  try {
    return database.prepare('SELECT id, name FROM categories ORDER BY name ASC').all() as Category[];
  } catch (e) {
    console.error("Failed to fetch categories:", e);
    return [];
  }
}

export function getBrandLogoFilename(brandName: string): string | undefined {
  if (!brandName) return undefined;
  const brandsDir = path.resolve(process.cwd(), 'public/static/logos/brands');
  if (!fs.existsSync(brandsDir)) return undefined;

  const exactPath = path.join(brandsDir, `${brandName}.png`);
  if (fs.existsSync(exactPath)) return `${brandName}.png`;

  const normalize = (s: string) => s.trim().toLowerCase().replace(/[\W_]+/g, '');
  const b = normalize(brandName);
  if (!b) return undefined;

  try {
    const files = fs.readdirSync(brandsDir);
    for (const file of files) {
      if (!file.endsWith('.png')) continue;
      const fNorm = normalize(file.replace('.png', ''));
      if (!fNorm) continue;
      if (b === fNorm || fNorm.includes(b) || b.includes(fNorm)) {
        return file;
      }
    }
  } catch (e) {
    // Ignore read errors
  }
  return undefined;
}

export function getBrands(): Brand[] {
  const database = getDb();
  if (!database) return [];
  try {
    const brands = database.prepare('SELECT id, name FROM brands ORDER BY name ASC').all() as Brand[];
    return brands.map(brand => ({
      ...brand,
      logo_filename: getBrandLogoFilename(brand.name)
    }));
  } catch (e) {
    console.error("Failed to fetch brands:", e);
    return [];
  }
}

export function getPublicProducts(): Product[] {
  const database = getDb();
  if (!database) return [];
  try {
    return database.prepare(`
      SELECT p.id, p.name, p.category_id, p.brand, p.unit, p.image_url, p.is_public, c.name as category_name
      FROM products p
      LEFT JOIN categories c ON p.category_id = c.id
      WHERE p.is_public = 1
      ORDER BY p.name ASC
    `).all() as Product[];
  } catch (e) {
    console.error("Failed to fetch products:", e);
    return [];
  }
}
