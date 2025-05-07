@bp.route('/extras/<int:batch_id>', methods=['POST'])
def save_batch_extras(batch_id):
    data = request.json
    extras = data.get('extras', [])

    batch = Batch.query.get_or_404(batch_id)

    # Add new extras without clearing existing ones
    for extra in extras:
        new_extra = BatchExtraIngredient(
            batch_id=batch_id,
            ingredient_id=extra['ingredient_id'],
            quantity=extra['quantity'],
            unit=extra['unit'],
            cost_per_unit=extra['cost_per_unit']
        )
        db.session.add(new_extra)

    db.session.commit()
    return jsonify({'status': 'success'})