#!/usr/bin/env python3
"""Convert prototype JSON to reviewable Odoo CSVs; never connects to Odoo."""
import argparse
import csv
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path


def percent(value):
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('Porcentaje inválido: %r' % value) from exc
    if not number.is_finite() or not 0 <= number <= 100:
        raise ValueError('Porcentaje fuera de rango: %r' % value)
    return str(number)


def convert(data, mapping):
    company = mapping['company_xmlid']
    currency = mapping['currency_xmlid']
    clients = data.get('clients')
    if clients is None:
        if data.get('format') != 'soles-client-discounts-v1':
            raise ValueError('Formato desconocido. Use exportación JSON v1 o padrón con clients.')
        clients = [data]
    partners, rules, profile_keys = [], [], set()
    seen = set()
    for client in clients:
        name = client.get('client', '')
        source_id = client.get('id') or name
        partner = mapping['clients'].get(source_id) or mapping['clients'].get(name)
        if not partner:
            raise ValueError('Cliente sin ID externo explícito: %s / %s' % (source_id, name))
        if partner in seen:
            raise ValueError('Dos clientes de origen resuelven al mismo contacto: ' + partner)
        seen.add(partner)
        profile = client.get('moduleProfile', '')
        profiles = mapping.get('profiles', {})
        if profile and profile not in profiles:
            raise ValueError('Perfil sin mapeo explícito: ' + profile)
        partners.append({'id': partner, 'soles_segment_id/id': profiles[profile]['segment_xmlid'] if profile else ''})
        if profile:
            profile_keys.add(profile)
        for index, rule in enumerate(client.get('rules', [])):
            category, brand = rule.get('category', ''), rule.get('brand', '')
            skus = [s.strip() for s in rule.get('skus', '').split(',') if s.strip()]
            if not category and not brand and not skus and rule.get('discount', '') in ('', None):
                continue  # Empty UI row.
            if not category and not brand and not skus:
                raise ValueError('Regla sin criterios: %s, fila %d' % (name, index + 1))
            try:
                category_id = mapping['families'][category] if category else ''
                brand_id = mapping['brands'][brand] if brand else ''
                product_ids = [mapping['skus'][sku] for sku in skus]
            except KeyError as exc:
                raise ValueError('Categoría, marca o SKU sin mapeo: ' + str(exc)) from exc
            rule_profile = rule.get('profile')
            rate = profiles[rule_profile]['discount_pct'] if rule_profile else rule.get('discount')
            key = hashlib.sha256((str(source_id) + ':' + str(rule.get('id', index))).encode()).hexdigest()[:20]
            rules.append({'id': 'soles_import.rule_' + key, 'name': '%s · regla %d' % (name, index + 1),
                          'company_id/id': company, 'currency_id/id': currency, 'sequence': 10,
                          'state': 'draft', 'stage': 'base', 'scope': 'partner', 'partner_id/id': partner,
                          'segment_id/id': '', 'method': 'list', 'discount_pct': percent(rate),
                          'family_id/id': category_id, 'brand_id/id': brand_id,
                          'product_ids/id': ','.join(product_ids), 'notes': rule.get('notes', ''), 'justification': 'Migración del HTML pendiente de revisión comercial'})
    for profile in sorted(profile_keys):
        p = mapping['profiles'][profile]
        rules.append({'id': p['rule_xmlid'], 'name': 'Perfil ' + profile, 'company_id/id': company,
                      'currency_id/id': currency, 'sequence': 10, 'state': 'draft', 'stage': 'base', 'scope': 'segment',
                      'partner_id/id': '', 'segment_id/id': p['segment_xmlid'], 'method': 'list',
                      'discount_pct': percent(p['discount_pct']), 'family_id/id': p['family_xmlid'],
                      'brand_id/id': '', 'product_ids/id': '', 'notes': 'Perfil migrado con tasa explícita del mapeo', 'justification': 'Perfil mapeado explícitamente; revisar antes de publicar'})
    return partners, rules


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('mapping', type=Path)
    parser.add_argument('output', type=Path, help='Nueva carpeta de salida; no debe existir')
    args = parser.parse_args()
    source = args.input.read_bytes()
    partner_rows, rule_rows = convert(json.loads(source), json.loads(args.mapping.read_text()))
    args.output.mkdir(parents=True, exist_ok=False)
    for filename, rows in [('partners.csv', partner_rows), ('rules.csv', rule_rows)]:
        with (args.output / filename).open('w', newline='', encoding='utf-8-sig') as stream:
            if rows:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
    (args.output / 'audit.json').write_text(json.dumps({'source_sha256': hashlib.sha256(source).hexdigest(),
        'clients': len(partner_rows), 'rules': len(rule_rows), 'quotes_imported': 0,
        'warning': 'Borradores para revisión. Mapear categorías del HTML a familias comerciales independientes; los perfiles no equivalen automáticamente a segmentos. No publicar hasta validar reglas y acuerdos. Sin conexión a Odoo.'}, ensure_ascii=False, indent=2))
    print('Generados %d clientes y %d reglas para revisión.' % (len(partner_rows), len(rule_rows)))


if __name__ == '__main__':
    main()
