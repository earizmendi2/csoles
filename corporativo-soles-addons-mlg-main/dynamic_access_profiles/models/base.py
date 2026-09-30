import ast

from lxml import etree

from odoo import api, models


class Base(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super().get_view(view_id, view_type, **options)
        view_scope_fields = {
            'form': 'apply_form',
            'list': 'apply_list',
            'tree': 'apply_list',
            'kanban': 'apply_kanban',
        }
        scope_field = view_scope_fields.get(view_type)
        if not scope_field or self.env.su or not result.get('arch'):
            return result

        configurations = self.env.user.sudo().profile_ids.mapped(
            'model_access_ids'
        ).filtered(
            lambda rule: rule.model_id.model == self._name
        )
        restrictions = configurations.filtered(lambda rule: rule[scope_field])
        conditional_rules = configurations.mapped('field_ids').filtered(
            lambda rule: rule.is_conditional and rule.condition_domain
        )
        button_rules = configurations.mapped('button_rule_ids').filtered('hide')
        if not restrictions and not conditional_rules and not button_rules:
            return result

        view = etree.fromstring(result['arch'])
        if any(restrictions.mapped('disable_create')):
            view.set('create', 'false')
        if any(restrictions.mapped('disable_edit')):
            view.set('edit', 'false')
        if any(restrictions.mapped('disable_delete')):
            view.set('delete', 'false')

        dependency_fields = set()
        for rule in conditional_rules:
            expression, dependencies = self._domain_to_modifier(
                rule.condition_domain
            )
            dependency_fields.update(dependencies)
            modifier = (
                'required' if rule.is_required
                else 'invisible' if rule.is_invisible
                else 'readonly'
            )
            for node in view.xpath(
                ".//field[@name=$field_name]",
                field_name=rule.field_id.name,
            ):
                previous = node.get(modifier)
                if previous and previous not in {'False', 'false', '0'}:
                    expression_to_set = f'({previous}) or ({expression})'
                else:
                    expression_to_set = expression
                node.set(modifier, expression_to_set)

        present_fields = set(view.xpath('.//field/@name'))
        for field_name in sorted(dependency_fields - present_fields):
            dependency = etree.Element('field')
            dependency.set('name', field_name)
            dependency.set('invisible', 'True')
            view.insert(0, dependency)

        for rule in button_rules:
            button = rule.button_id
            if button.view_type != view_type:
                continue
            if view_id and button.view_id.id != view_id:
                continue
            for node in view.xpath(
                ".//button[@name=$button_name]",
                button_name=button.technical_name,
            ):
                if node.get('type', 'object') != button.button_type:
                    continue
                is_smart = 'oe_stat_button' in node.get('class', '').split()
                if is_smart == button.is_smart_button:
                    node.set('invisible', 'True')

        result = dict(result)
        result['arch'] = etree.tostring(view, encoding='unicode')
        return result

    @api.model
    def _domain_to_modifier(self, domain_text):
        domain = ast.literal_eval(domain_text or '[]')
        dependencies = set()

        def leaf_to_expression(leaf):
            field_name, operator, value = leaf
            dependencies.add(field_name)
            field_expr = field_name
            value_expr = repr(value)
            comparison_operators = {
                '=': '==',
                '!=': '!=',
                '>': '>',
                '>=': '>=',
                '<': '<',
                '<=': '<=',
                'in': 'in',
                'not in': 'not in',
            }
            if operator in comparison_operators:
                return f'{field_expr} {comparison_operators[operator]} {value_expr}'
            if operator == '=?':
                return 'True' if not value else f'{field_expr} == {value_expr}'
            if operator in {'like', 'ilike', 'not like', 'not ilike'}:
                needle = str(value).replace('%', '')
                if operator in {'ilike', 'not ilike'}:
                    expression = (
                        f'{needle.lower()!r} in ({field_expr} or "").lower()'
                    )
                else:
                    expression = f'{needle!r} in ({field_expr} or "")'
                return f'not ({expression})' if operator.startswith('not ') else expression
            raise ValueError(f'Unsupported domain operator: {operator}')

        def parse_tokens(tokens, index=0):
            token = tokens[index]
            if isinstance(token, str) and token in {'&', '|'}:
                left, next_index = parse_tokens(tokens, index + 1)
                right, next_index = parse_tokens(tokens, next_index)
                joiner = 'and' if token == '&' else 'or'
                return f'({left}) {joiner} ({right})', next_index
            if token == '!':
                child, next_index = parse_tokens(tokens, index + 1)
                return f'not ({child})', next_index
            if isinstance(token, list) and not (
                len(token) == 3 and isinstance(token[0], str)
            ):
                return domain_to_expression(token), index + 1
            return leaf_to_expression(token), index + 1

        def domain_to_expression(tokens):
            expressions = []
            index = 0
            while index < len(tokens):
                expression, index = parse_tokens(tokens, index)
                expressions.append(expression)
            return ' and '.join(f'({item})' for item in expressions)

        return domain_to_expression(domain), dependencies
