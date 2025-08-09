
const path = require('path');

module.exports = {
  mode: 'development',
  entry: {
    main: './core/BatchTrackApp.js',
    batches: './batches/batch_form.js',
    inventory: './inventory/inventory_adjust.js',
    products: './products/product_inventory.js',
    recipes: './recipes/recipe_form.js'
  },
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: '[name].bundle.js',
    clean: true
  },
  module: {
    rules: [
      {
        test: /\.js$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: ['@babel/preset-env']
          }
        }
      }
    ]
  },
  optimization: {
    splitChunks: {
      chunks: 'all',
      cacheGroups: {
        vendor: {
          test: /[\\/]node_modules[\\/]/,
          name: 'vendors',
          chunks: 'all'
        }
      }
    }
  },
  devtool: 'source-map'
};
