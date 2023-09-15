from flask import Flask, render_template, request, redirect, url_for, flash
from markupsafe import Markup
from collections import Counter
from flask_bootstrap import Bootstrap

import boto3
import re
import os

if 'AWS_EXECUTION_ENV' in os.environ:
    # Running on AWS Elastic Beanstalk
    application = app = Flask(__name__)
    application.config['SECRET_KEY'] = os.environ.get(
        'FLASK_SECRET_KEY',
        '\xf0?a\x9a\\\xff\xd4;\x0c\xcbHi'
    )
    Bootstrap(application)
    session = boto3.Session()
else:
    # Running locally
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get(
        'FLASK_SECRET_KEY',
        '\xf0?a\x9a\\\xff\xd4;\x0c\xcbHi'
    )
    Bootstrap(app)
    session = boto3.Session(profile_name='swu-admin')


dynamodb = session.client('dynamodb',
                        region_name='us-east-1')


def publish_feedback_to_sns(message):
    """
    Publishes a message to an SNS Topic
    """
    sns = session.client('sns', region_name='us-east-1')
    topic_arn = os.environ.get('FEEDBACK_ARN')
    message = f"Message: {message}"

    sns.publish(
        TopicArn=topic_arn,
        Message=message
    )

def get_card(set_id, card_number):
    """
    Given a set id and card number, return the matching card
    """
    response = dynamodb.query(
        TableName='Cards2',
        KeyConditionExpression='setId = :set_id and cardNumber = :card_number',
        ExpressionAttributeValues={
            ':set_id': {'S': set_id},
            ':card_number': {'S': card_number}
        }
    )

    items = response['Items']

    if items:
        # setID and cardNumber are unique so it's safe to just grab the first one
        return process_item(items[0])
    else:
        # Card not found
        return None


def search_cards(search_input, sort_field='name', sort_order='asc', leader='', base=''):
    """
    Search the Cards table using the input provided by the user
    Return any matching cards, in the manner specified by sort_field and sort_order
    """
    expressions = []
    current_expression = ""
    quote_stack = []

    result_string = ""

    for char in search_input:
        if char == " " and not quote_stack:
            if current_expression:
                expressions.append(current_expression)
                current_expression = ""
        elif char == "'":
            if quote_stack and quote_stack[-1] == "'":
                quote_stack.pop()
            else:
                quote_stack.append("'")
        elif char == '"':
            if quote_stack and quote_stack[-1] == '"':
                quote_stack.pop()
            else:
                quote_stack.append('"')
        else:
            current_expression += char

    if current_expression:
        expressions.append(current_expression)

    # Combine adjacent expressions inside quotes into a single expression
    combined_expressions = []
    temp_expression = ""
    for expression in expressions:
        if quote_stack:
            if temp_expression:
                temp_expression += " " + expression
                if quote_stack[-1] == expression[0] and expression[-1] == expression[0]:
                    combined_expressions.append(temp_expression.strip('"').strip("'"))
                    temp_expression = ""
            else:
                temp_expression = expression

        if not quote_stack and temp_expression:
            combined_expressions.append(temp_expression.strip('"').strip("'"))
            temp_expression = ""

    if temp_expression:
        combined_expressions.append(temp_expression.strip('"').strip("'"))

    # Use the combined expressions for further processing
    print(combined_expressions)

    # Construct the filter expressions for DynamoDB
    filter_expressions = []
    expression_values = {}
    expression_attribute_names = {}
    print(expressions)
    filter_expression_groups = []
    current_group = []

    for expression in expressions:
        filter_expression = ''
        parentheses_removed = 0
        expression = expression.lower()
        if expression == 'or':
            result_string += " or "
            if current_group:
                filter_expression_groups.append(' AND '.join(current_group))
                current_group = []
            continue
        elif expression == 'and':
            result_string += " and "
            continue
        elif expression.startswith('('):
            original_length = len(expression)
            expression = expression.lstrip('(')
            stripped_length = len(expression)
            parentheses_removed = original_length - stripped_length
            for x in range(parentheses_removed):
                result_string += " ("
                filter_expression = '('
            parentheses_removed = 0
        elif expression.endswith(')'):
            original_length = len(expression)
            expression = expression.rstrip(')')
            stripped_length = len(expression)
            parentheses_removed = original_length - stripped_length

        if re.search(r'(?:a|aspect)(?:<=|<|>|>=|=|:)(.+)', expression):
            attribute_name, comparison_operator, attribute_value = parse_numerical_expression(
                expression)

            if comparison_operator == ':':
                comparison_operator = '>='

            result_string += " the aspect " + comparison_operator + " " + attribute_value

            if attribute_value in ('vigilance', 'blue'):
                attribute_value = 'b'
            elif attribute_value in ('command', 'green'):
                attribute_value = 'g'
            elif attribute_value in ('aggression', 'red'):
                attribute_value = 'r'
            elif attribute_value in ('cunning', 'yellow'):
                attribute_value = 'y'
            elif attribute_value in ('heroism', 'white'):
                attribute_value = 'w'
            elif attribute_value in ('villainy', 'black'):
                attribute_value = 'k'

            expression_attribute_values = {}

            aspect_counts = {}  # A dictionary to store the counts of each aspect

            # Define the possible aspect abbreviations
            possible_aspects = ['b', 'g', 'r', 'y', 'w', 'k']

            # Initialize counts for all aspects to 0
            for aspect in possible_aspects:
                aspect_counts[aspect] = 0

            # Count the occurrences of each aspect in the string
            for letter in attribute_value:
                if letter in possible_aspects:
                    aspect_counts[letter] += 1

            filter_expression_parts = []
            # Loop through the aspect counts dictionary to construct conditions
            for aspect, count in aspect_counts.items():
                if comparison_operator in ['>', '>='] and count == 0:
                    continue
                # Define placeholders for expression attribute names and values
                expression_attr_name = f'#count_{aspect}'
                expression_attr_value = f':val_{aspect}'

                if comparison_operator == '>':
                    filter_expression_parts.append(f'{expression_attr_name} >= {expression_attr_value}')
                elif comparison_operator == '<':
                    filter_expression_parts.append(f'{expression_attr_name} <= {expression_attr_value}')
                else:

                    # Add condition for aspect count
                    filter_expression_parts.append(f'{expression_attr_name} {comparison_operator} {expression_attr_value}')

                # Populate expression attribute names and values
                expression_attribute_values[expression_attr_value] = {'N': str(count)}
                expression_attribute_names[expression_attr_name] = f'{aspect}Count'

            if comparison_operator == '>':
                # Construct the condition for the sum of aspect attributes
                filter_expression_parts.append(f'#total_count > :val_total')
                expression_attribute_values[':val_total'] = {'N': str(len(attribute_value))}
                expression_attribute_names['#total_count'] = 'totalCount'
            if comparison_operator == '<':
                # Construct the condition for the sum of aspect attributes
                filter_expression_parts.append(f'#total_count < :val_total')
                expression_attribute_values[':val_total'] = {'N': str(len(attribute_value))}
                expression_attribute_names['#total_count'] = 'totalCount'

            # Combine all filter conditions with 'AND'
            filter_expression += ' AND '.join(filter_expression_parts)
            print(filter_expression)
            print(expression_attribute_values)
            print(expression_attribute_names)

            expression_values.update(expression_attribute_values)
            
        elif re.match(r'^\w+(?:<=|>=|=|!=|<|>)\d+$', expression):

            # Parse numerical expressions
            attribute_name, comparison_operator, attribute_value = parse_numerical_expression(
                expression)

            if attribute_name == 'p':
                attribute_name = 'power'
                result_string += " the power " 
            elif attribute_name == 'h':
                attribute_name = 'HP'
                result_string += " the hp " 
            elif attribute_name == 'c':
                attribute_name = 'cost'
                result_string += " the cost " 

            result_string += comparison_operator + " " + attribute_value
            filter_expression += construct_filter_expression(
                attribute_name, comparison_operator)
            expression_values.update(construct_expression_value(
                attribute_name, attribute_value))
            expression_attribute_names.update(
                construct_expression_attribute_name(attribute_name))

        else:
            match = re.search(r'\b(?:t|text):(.+)', expression)
            trait = re.search(r'\b(?:tr|trait):(.+)', expression)
            type = re.search(r'\b(?:ty|type):(.+)', expression)
            arena = re.search(r'\b(?:ar|arena):(.+)', expression)
            rarity = re.search(r'\b(?:r|rarity):(.+)', expression)
            card_set = re.search(r'\b(?:s|set):(.+)', expression)
            artist = re.search(r'\b(?:art|artist):(.+)', expression)
            name = re.search(r'(?:name|title):(.+)', expression)

            if match:
                attribute_name = 'searchText'
                comparison_operator = 'contains'
                attribute_value = match.group(1).lower()
                result_string += " the text includes " + attribute_value
                filter_expression += f"contains (#{attribute_name}, :{attribute_name})"
                expression_values.update(construct_expression_value(
                    attribute_name, attribute_value, is_numeric=False))
                expression_attribute_names.update(
                    construct_expression_attribute_name(attribute_name))
            elif artist:
                attribute_name = 'artistSearch'
                comparison_operator = 'contains'
                attribute_value = expression.split(':', 1)[1].strip().lower()
                result_string += " the artist name includes " + attribute_value
                filter_expression += f"contains (#{attribute_name}, :{attribute_name})"
                expression_values.update(construct_expression_value(
                    attribute_name, attribute_value, is_numeric=False))
                expression_attribute_names.update(
                    construct_expression_attribute_name(attribute_name))
            elif card_set:
                attribute_name = 'setId'
                comparison_operator = '='
                attribute_value = expression.split(':', 1)[1].strip().upper()
                result_string += " the set is " + attribute_value
                filter_expression += f"contains (#{attribute_name}, :{attribute_name})"
                expression_values.update(construct_expression_value(
                    attribute_name, attribute_value, is_numeric=False))
                expression_attribute_names.update(
                    construct_expression_attribute_name(attribute_name))
            elif trait:
                attribute_name = 'traits'
                comparison_operator = 'contains'
                
                attribute_value = expression.split(':', 1)[1].strip().upper()
                result_string += " the traits include " + attribute_value
                attribute_placeholder = attribute_name + '_' + attribute_value
                attribute_placeholder = re.sub(r'[ "\']', '_', attribute_placeholder)


                filter_expression += f"contains ({attribute_name}, :{attribute_placeholder})"
                expression_values.update(construct_expression_value(
                    attribute_placeholder, attribute_value, is_numeric=False))
            elif type:
                attribute_name = 'type'
                attribute_value = expression.split(':', 1)[1].strip().lower().title()
                result_string += " the type includes " + attribute_value
                attribute_placeholder = attribute_name + '_' + attribute_value
                attribute_placeholder = re.sub(r'[ "\']', '_', attribute_placeholder)
                comparison_operator = 'contains'
                filter_expression += f"contains (#{attribute_name}, :{attribute_placeholder})"
                
                expression_values.update(construct_expression_value(
                    attribute_placeholder, attribute_value, is_numeric=False))
                expression_attribute_names.update(
                    construct_expression_attribute_name(attribute_name))
            elif arena:
                attribute_name = 'arenas'
                comparison_operator = 'contains'
                
                attribute_value = expression.split(':', 1)[1].strip().upper().title()
                result_string += " the arena includes " + attribute_value
                attribute_placeholder = attribute_name + '_' + attribute_value
                attribute_placeholder = re.sub(r'[ "\']', '_', attribute_placeholder)


                filter_expression += f"contains ({attribute_name}, :{attribute_placeholder})"
                expression_values.update(construct_expression_value(
                    attribute_placeholder, attribute_value, is_numeric=False))
            elif rarity:
                attribute_name = 'rarity'
                attribute_value = expression.split(':', 1)[1].strip().upper()
                result_string += " the rarity includes " + attribute_value
                attribute_placeholder = attribute_name + '_' + attribute_value
                attribute_placeholder = re.sub(r'[ "\']', '_', attribute_placeholder)
                comparison_operator = 'contains'
                filter_expression += f"contains (#{attribute_name}, :{attribute_placeholder})"
                
                expression_values.update(construct_expression_value(
                    attribute_placeholder, attribute_value, is_numeric=False))
                expression_attribute_names.update(
                    construct_expression_attribute_name(attribute_name))
            elif name:
                attribute_name = 'searchName'
                comparison_operator = 'contains'
                attribute_value = expression.split(':', 1)[1].strip().lower()
                result_string += " the name includes " + attribute_value
                filter_expression += f"contains (#{attribute_name}, :{attribute_name})"
                expression_values.update(construct_expression_value(
                    attribute_name, attribute_value, is_numeric=False))
                expression_attribute_names.update(
                    construct_expression_attribute_name(attribute_name))
            else:
                attribute_name = 'searchName'
                attribute_placeholder = attribute_name + '_' + expression
                attribute_placeholder = re.sub(r'[ "\']', '_', attribute_placeholder)
                comparison_operator = 'contains'
                attribute_value = expression.lower()
                result_string += " the name includes " + attribute_value
                filter_expression += f"contains (#{attribute_name}, :{attribute_placeholder})"
                
                expression_values.update(construct_expression_value(
                    attribute_placeholder, attribute_value, is_numeric=False))
                expression_attribute_names.update(
                    construct_expression_attribute_name(attribute_name))

        for x in range(parentheses_removed):
            filter_expression += ')'
            result_string += ' )'
        filter_expressions.append(filter_expression)
        current_group.append(filter_expression)

    if current_group:
        filter_expression_groups.append(' AND '.join(current_group))

    filter_expression = ' OR '.join(filter_expression_groups)

    if not expression_values:
        response = dynamodb.scan(
            TableName='Cards2'
        )
    elif not expression_attribute_names:
        response = dynamodb.scan(
            TableName='Cards2',
            FilterExpression=filter_expression,
            ExpressionAttributeValues=expression_values
        )
    else:
        # Execute the query and retrieve the matching items
        response = dynamodb.scan(
            TableName='Cards2',
            FilterExpression=filter_expression,
            ExpressionAttributeValues=expression_values,
            ExpressionAttributeNames=expression_attribute_names
        )

    # Process the response and extract the matching cards
    cards = process_response(response)
    if leader and base:
        set_card = leader.split('-')
        set_id = set_card[0]
        card_number = set_card[1]
        leader_card = get_card(set_id, card_number)

        set_card = base.split('-')
        set_id = set_card[0]
        card_number = set_card[1]

        base_card = get_card(set_id, card_number)

        l_aspects = leader_card['aspects']
        b_aspects = base_card['aspects']
        leader_base_aspects = l_aspects + b_aspects
        leader_base_counts = Counter(leader_base_aspects)

        for card in cards:
            if card['type'] in ('Leader', 'Base'):
                card['penalty'] = 'N/A'
                continue
            
            aspects = card['aspects']
            aspect_counts = Counter(aspects)
            
            penalty = 0
            for aspect, count in aspect_counts.items():
                if leader_base_counts[aspect] < count:
                    penalty += 2 * (count - leader_base_counts[aspect])

            # Add the 'penalty' value to the card
            card['penalty'] = penalty
    else:
        leader_card = None
        base_card = None
    # Determine the number of matching cards
    num_cards = len(cards)

    # Extract the search expressions from the search input
    search_expressions = []

    # Generate the sentence describing the search results
    search_description = f"{num_cards} {'card' if num_cards == 1 else 'cards'} where" + result_string
    search_expressions.append(search_input)

    reverse_order = sort_order == 'desc'
    if (sort_field == None) or (sort_field == 'name'):
        sorted_cards = sorted(cards, key=lambda x: x.get(
            'name', 0), reverse=reverse_order)
    elif (sort_field in ['power', 'cost', 'hp']):
        for card in cards:
            print(card['hp'])
        sorted_cards = sorted(cards, key=lambda x: int(
            x.get(sort_field, 0) or 0), reverse=reverse_order)
    elif (sort_field == 'setnumber'):
        if reverse_order:
            sorted_cards = cards
            sorted_cards.reverse()
        else:
            sorted_cards = cards
    elif (sort_field == 'type'):
        sorted_cards = sorted(cards, key=lambda x: x.get(
            'type', 0), reverse=reverse_order)
    elif (sort_field == 'rarity'):
        sorted_cards = sorted(cards, key=lambda x: x.get(
            'rarity', 0), reverse=reverse_order)
    elif (sort_field == 'traits'):
        sorted_cards = sorted(cards, key=lambda x: x.get(
            'traits', 0), reverse=reverse_order)
    elif (sort_field == 'aspects'):
        sorted_cards = sorted(cards, key=lambda x: x.get(
            'aspect_icons', 0), reverse=reverse_order)
    elif (sort_field == 'artist'):
        sorted_cards = sorted(cards, key=lambda x: x.get(
            'artist', 0), reverse=reverse_order)
    elif (sort_field == 'arenas'):
        sorted_cards = sorted(cards, key=lambda x: x.get(
            'arenas', 0), reverse=reverse_order)
    elif (sort_field == 'penalty'):
        sorted_cards = sorted(cards, key=lambda x: float('inf') if x.get(
            'penalty') == 'N/A' else int(x.get('penalty', 0)), reverse=reverse_order)
    else:
        sorted_cards = cards
    return sorted_cards, search_description, leader_card, base_card


def parse_numerical_expression(expression):
    # Use regular expressions to extract attribute name, comparison operator, and value
    match = re.match(r'([pchaPCHA])((?:<=|>=|<|>|=|!=|:)?)(\w+)', expression)
    attribute_name = match.group(1).lower()
    comparison_operator = match.group(2)
    attribute_value = match.group(3)
    if comparison_operator == '!=':
        comparison_operator = '<>'
    return attribute_name, comparison_operator, attribute_value


def construct_filter_expression(attribute_name, comparison_operator):
    # Construct the filter expression based on the attribute name and comparison operator
    return f'#{attribute_name} {comparison_operator} :value_{attribute_name}'


def construct_expression_value(attribute_name, attribute_value, is_numeric=True):
    expression_value = {}

    if is_numeric:
        # Assuming numeric attribute
        return {f':value_{attribute_name}': {'N': attribute_value}}
    else:
        expression_value[':' + attribute_name] = {'S': attribute_value}

    return expression_value


def construct_expression_attribute_name(attribute_name):
    # Construct the expression attribute name based on the attribute name
    return {f'#{attribute_name}': attribute_name}


def process_response(response):
    # Process the DynamoDB response and extract the matching cards
    items = response['Items']
    # print(items)
    cards = [process_item(item) for item in items]

    return cards


def process_item(item):
    # Process a single item from the DynamoDB response and return a card object
    # Extract the necessary attributes from the item
    card_set = item['setId']['S']
    number = item['cardNumber']['S']
    type = item['type']['S']
    front_art = item['frontArt']['S']
    v_front_art = item.get('verticalFrontArt', {}).get('S', None)
    rarity = item['rarity']['S']
    has_back = item['hasBack']['BOOL']
    power = item.get('power', {}).get('N', None)
    subtitle = item.get('subtitle', {}).get('S', None)
    text = item.get('textStyled', {}).get('S', None)
    cost = item.get('cost', {}).get('N', None)
    hp = item.get('HP', {}).get('N', None)
    name = item['name']['S']
    back_art = item.get('backArt', {}).get('S', None)
    artist = item.get('artist', {}).get('S', None)
    is_landscape = item.get('isLandscape', {}).get('BOOL', False)
    aspect_icons = []
    aspects_response = item.get('aspects', {}).get('L', [])
    aspects = [aspect['S'] for aspect in aspects_response]
    epic_action = item.get('epicActionStyled', {}).get('S', None)
    back_text = item.get('backTextStyled', {}).get('S', None)

    traits_response = item.get('traits', {}).get('L', [])
    traits = [traits['S'] for traits in traits_response]
    arenas = item.get('arenas', {}).get('SS', [])

    for aspect in aspects:
        aspect = aspect.lower()
        # Assuming aspect icons are named after their respective aspect names
        aspect_icon_path = f'/static/images/{aspect}.png'
        aspect_icons.append(aspect_icon_path)

    if subtitle is not None:
        name = name + ' - ' + subtitle

    # Create and return a card object
    card = {
        'set': card_set,
        'number': number,
        'front_art': front_art,
        'has_back': has_back,
        'back_art': back_art,
        'power': power,
        'name': name,
        'cost': cost,
        'hp': hp,
        'type': type,
        'rarity': rarity,
        'subtitle': subtitle,
        'is_landscape': is_landscape,
        'v_front_art': v_front_art,
        'aspect_icons': aspect_icons,
        'traits': traits,
        'artist': artist,
        'text': text,
        'arenas': arenas,
        'epic_action': epic_action,
        'back_text': back_text,
        'aspects': aspects
    }

    return card


@app.route('/', methods=['GET'])
def homepage():
    return render_template('index.html')


@app.route('/search', methods=['GET', 'POST'])
def search():
    search_input = request.args.get('q')
    sort_field = request.args.get('sort')
    sort_order = request.args.get('sortOrder')
    display_mode = request.args.get('display_mode')
    leader = request.args.get('leader')
    base = request.args.get('base')
    cards, result_string, leader, base = search_cards(search_input, sort_field, sort_order, leader, base)
    for card in cards:
        card.pop('back_text', None)
    # cards_json = json.dumps(cards, ensure_ascii=False, default=lambda x: None)
    # Pass the cards data to the template for rendering
    return render_template('search_results.html', cards=cards, result_string=result_string, sort_field=sort_field, sort_order=sort_order, q=search_input, display_mode=display_mode, leader=leader, base=base)


@app.route('/card/<string:set>/<string:number>/<string:name>')
def card(set, number, name):
    # Retrieve card information based on the set, number, and name
    # Render the card page template with the retrieved card information
    my_card = get_card(set, number)
    return render_template('card.html', set=set, number=number, name=name, card=my_card)

@app.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    message = request.form.get('message')

    # Process the feedback data, e.g., publish to SNS
    publish_feedback_to_sns(message)

    # Flash a success message
    flash('Your feedback has been submitted successfully!', 'success')

    # Redirect to the homepage after successful submission
    return redirect(url_for('homepage'))

@app.route('/syntax')
def syntax():
    return render_template('syntax.html')

@app.route('/api')
def api():
    return render_template('api.html')


@app.route('/feedback')
def feedback():
    return render_template('feedback.html')

@app.route('/resources')
def resources():
    return render_template('resources.html')

@app.route('/advanced')
def advanced():
    response = dynamodb.scan(
        TableName='Cards2'
    )

    # Retrieve unique traits from the items
    unique_traits = set('')
    unique_types = set('')
    leaders = []
    bases = []
    for item in response['Items']:
        if 'traits' in item:
            traits_list = item['traits']['L']
            traits = [traits['S'] for traits in traits_list]
            unique_traits.update(traits)
        if 'type' in item:
            type_list = item['type']['S']
            unique_types.add(type_list)

            if item['type'] == {'S': 'Leader'}:
                leader = {
                    'setId': item['setId']['S'],
                    'cardNumber': item['cardNumber']['S'],
                    'name': item['name']['S'],
                    'subtitle': item['subtitle']['S']
                }
                leaders.append(leader)
            elif item['type'] == {'S': 'Base'}:
                base = {
                    'setId': item['setId']['S'],
                    'cardNumber': item['cardNumber']['S'],
                    'name': item['name']['S']
                }
                bases.append(base)

    return render_template('advanced.html', unique_traits=sorted(unique_traits), leaders=leaders, bases=bases, unique_types=sorted(unique_types))

@app.route('/advanced_results', methods=['GET', 'POST'])
def advanced_results():
    aspects = request.form.getlist('aspect')
    aspect_opt = request.form.get('aspect-option')
    card_name = request.form.get('card-name')
    card_text = request.form.get('card-text')
    traits = request.form.getlist('trait[]')
    display_mode = request.form.get('display-option')
    sort_field = request.form.get('display-sort-column')
    stat_select_1 = request.form.get('stat-select-1')
    stat_select_2 = request.form.get('stat-select-2')
    stat_select_3 = request.form.get('stat-select-3')
    opeator_select_1 = request.form.get('operator-select-1')
    opeator_select_2 = request.form.get('operator-select-2')
    opeator_select_3 = request.form.get('operator-select-3')
    value_input_1 = request.form.get('value-input-1')
    value_input_2 = request.form.get('value-input-2')
    value_input_3 = request.form.get('value-input-3')
    chosen_leader = request.form.get('leader')
    chosen_base = request.form.get('base')
    partial_match = request.form.get('partial-match')
    arena = request.form.get('arena')
    artist = request.form.get('artist')
    rarities = request.form.getlist('rarity')

    traits_list = []
    types_list = []
    print(traits_list)

    for string in traits:
        if string.isupper():
            traits_list.append(string)
        elif string != '':
            types_list.append(string)


    search_input = ''
    if aspects:
        search_input = 'a' + aspect_opt + ''.join(aspects)
    if artist:
        search_input += ' artist:' + artist
    if rarities:
        search_input += ' (r:' + ' OR r:'.join(rarities)  + ' )'
    if card_name:
        search_input += ' ' + card_name
    if arena:
        search_input += ' arena:' + arena
    if traits_list or types_list:
        if partial_match == 'on':
            search_input += ' ('
            count = 0
            if traits_list:
                for trait in traits_list:
                    if count > 0:
                        search_input += ' or tr:"' + trait + '"'
                    else:
                        search_input += ' tr:"' + trait + '"'
                    count += 1
            if types_list:
                for type in types_list:
                    if count > 0:
                        search_input += ' or type:' + type
                    else:
                        search_input += ' type:' + type
                    count += 1
            search_input += ' )'
        else:

            if traits_list:
                for trait in traits_list:
                    search_input += ' tr:"' + trait + '"'
            if types_list:
                for type in types_list:
                    search_input += ' type:' + type

    if card_text:
        search_input += ' t:' + card_text
    if value_input_1:
        search_input += ' ' + stat_select_1 + opeator_select_1 + value_input_1
    if value_input_2:
        search_input += ' ' + stat_select_2 + opeator_select_2 + value_input_2
    if value_input_3:
        search_input += ' ' + stat_select_3 + opeator_select_3 + value_input_3

    sort_order = 'asc'
    return redirect(url_for('search', q=search_input, sort=sort_field, sort_order=sort_order, display_mode=display_mode, leader=chosen_leader, base=chosen_base))

@app.template_filter('replace_aspects')
def replace_aspects(text):
    aspect_icons = {
        'Heroism': 'heroism.png',
        'Vigilance': 'vigilance.png',
        'Villainy': 'villainy.png',
        'Command': 'command.png',
        'Cunning': 'cunning.png',
        'Aggression': 'aggression.png'
    }

    for aspect, icon_filename in aspect_icons.items():
        placeholder = '{{' + aspect + '}}'
        icon_path = url_for('static', filename='images/' + icon_filename)
        text = text.replace(
            placeholder, f'<span class="aspect-icon"><img src="{icon_path}" alt="{aspect} icon"></span>')

    return Markup(text)


if __name__ == '__main__':
    app.run(debug=False)
