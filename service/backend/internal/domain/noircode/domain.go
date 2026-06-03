// Package noircode is the gateway domain for NoiR Code encode/decode. It owns
// validation and the public contract; the heavy image work is delegated to the
// Imaging outbound port (the Python reference implementation).
package noircode

// Domain holds the encode/decode use cases. It depends only on the Imaging and
// Fetcher outbound ports, so the REST adapter → domain → (imaging, fetcher)
// dependency chain is compile-time checked.
type Domain struct {
	imaging Imaging
	fetcher Fetcher
}

// New builds the noircode domain over an Imaging backend and a Fetcher for
// decode-by-URL.
func New(imaging Imaging, fetcher Fetcher) *Domain {
	return &Domain{imaging: imaging, fetcher: fetcher}
}

// Compile-time assertion that *Domain satisfies the inbound port.
var _ Service = (*Domain)(nil)
